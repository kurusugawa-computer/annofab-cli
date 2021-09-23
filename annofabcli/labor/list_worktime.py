import argparse
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import annofabapi
import more_itertools
import pandas
from annofabapi.models import Project, ProjectMember
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_list_from_args

logger = logging.getLogger(__name__)


class TargetColumn(Enum):
    ACTUAL_WORKTIME_HOUR = "actual_worktime_hour"
    PLAN_WORKTIME_HOUR = "plan_worktime_hour"


@dataclass(frozen=True)
class LaborWorktime(DataClassJsonMixin):
    """
    労務管理情報
    """

    date: str
    organization_id: str
    organization_name: str
    project_id: str
    project_title: str
    account_id: str
    user_id: Optional[str]
    username: Optional[str]
    biography: Optional[str]
    actual_worktime_hour: float
    """労務管理画面の実績作業時間"""
    plan_worktime_hour: float
    """労務管理画面の予定作業時間"""


BASE_COLUMNS = [
    "date",
    "organization_id",
    "organization_name",
    "project_id",
    "project_title",
    "account_id",
    "user_id",
    "username",
    "biography",
]


class ListLaborWorktimeMain:
    def __init__(self, service: annofabapi.Resource, target_columns: Set[TargetColumn]):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.target_columns = target_columns

    def is_target_labor(self, labor: Dict[str, Any]) -> bool:
        """集計対象の労務管理情報か否か"""
        # 個人に紐付かないデータの場合は除去
        if labor["account_id"] is None:
            return False

        if self.target_columns == {TargetColumn.ACTUAL_WORKTIME_HOUR, TargetColumn.PLAN_WORKTIME_HOUR}:
            # 実績作業時間と予定作業時間の両方が無効な場合は除去
            if (labor["actual_worktime"] is None or labor["actual_worktime"] == 0) and (
                labor["plan_worktime"] is None or labor["plan_worktime"] == 0
            ):
                return False

        elif self.target_columns == {TargetColumn.ACTUAL_WORKTIME_HOUR}:
            if labor["actual_worktime"] is None or labor["actual_worktime"] == 0:
                return False

        elif self.target_columns == {TargetColumn.PLAN_WORKTIME_HOUR}:
            if labor["plan_worktime"] is None or labor["plan_worktime"] == 0:
                return False

        return True

    @staticmethod
    def _get_labor_worktime(
        labor: Dict[str, Any],
        *,
        member: Optional[ProjectMember],
        project_title: str,
        organization_name: str,
    ) -> LaborWorktime:
        new_labor = LaborWorktime(
            date=labor["date"],
            organization_id=labor["organization_id"],
            organization_name=organization_name,
            project_id=labor["project_id"],
            project_title=project_title,
            account_id=labor["account_id"],
            user_id=member["user_id"] if member is not None else None,
            username=member["username"] if member is not None else None,
            biography=member["biography"] if member is not None else None,
            plan_worktime_hour=labor["plan_worktime"] if labor["plan_worktime"] is not None else 0,
            actual_worktime_hour=labor["actual_worktime"] if labor["actual_worktime"] is not None else 0,
        )
        return new_labor

    @staticmethod
    def get_project_title(project_list: List[Project], project_id: str) -> str:
        project = more_itertools.first_true(project_list, pred=lambda e: e["project_id"] == project_id)
        if project is not None:
            return project["title"]
        else:
            return ""

    def get_inaccessible_project_ids(self, labor_list: List[Dict[str, Any]]) -> List[str]:
        project_id_set = {labor["project_id"] for labor in labor_list}
        inaccessible_project_ids = []
        for project_id in project_id_set:
            project = self.service.wrapper.get_project_or_none(project_id)
            if project is None:
                logger.warning(f"project_id='{project_id}'のプロジェクトにアクセスできません。")
                inaccessible_project_ids.append(project_id)
        return inaccessible_project_ids

    def get_labor_list_from_organization_name(
        self,
        *,
        organization_name: str,
        start_date: str,
        end_date: str,
        account_id_list: Optional[List[str]],
    ) -> List[LaborWorktime]:
        organization = self.service.wrapper.get_organization_or_none(organization_name)
        if organization is None:
            logger.warning(f"organization_name='{organization_name}' の組織にアクセスできないため、スキップします。")
            return []

        organization_id = organization["organization_id"]

        if account_id_list is None:
            logger.debug(f"organization_name={organization_name}, {start_date}〜{end_date} の労務管理情報を取得しています。")
            labor_list = self.service.wrapper.get_labor_control_worktime(
                organization_id=organization_id, from_date=start_date, to_date=end_date
            )
        else:
            labor_list = []
            logger.debug(
                f"organization_name={organization_name}, {start_date}〜{end_date},"
                f"ユーザ{len(account_id_list)}件分の労務管理情報を取得しています。"
            )
            for account_id in account_id_list:
                tmp_labor_list = self.service.wrapper.get_labor_control_worktime(
                    organization_id=organization_id, from_date=start_date, to_date=end_date, account_id=account_id
                )
                labor_list.extend(tmp_labor_list)

        project_list = self.service.wrapper.get_all_projects_of_organization(organization_name)

        new_labor_list = []

        # 労務管理情報の絞り込み
        labor_list = [e for e in labor_list if self.is_target_labor(e)]

        inaccessible_project_ids = self.get_inaccessible_project_ids(labor_list)
        for labor in labor_list:
            if labor["project_id"] not in inaccessible_project_ids:
                try:
                    member = self.facade.get_project_member_from_account_id(labor["project_id"], labor["account_id"])
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"project_id={labor['project_id']}: メンバ一覧を取得できませんでした。")
                    member = None
            else:
                member = None

            project_title = self.get_project_title(project_list, labor["project_id"])

            new_labor = self._get_labor_worktime(
                labor,
                member=member,
                project_title=project_title,
                organization_name=organization_name,
            )
            new_labor_list.append(new_labor)

        logger.info(f"'{organization_name}'組織の労務管理情報の件数: {len(new_labor_list)}")

        return new_labor_list

    def get_labor_list_from_project_id(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
        *,
        account_id_list: Optional[List[str]],
    ) -> List[LaborWorktime]:
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id='{project_id}' のプロジェクトにアクセスできないため、スキップします。")
            return []

        project_title = project["title"]

        organization, _ = self.service.api.get_organization_of_project(project_id)
        organization_name = organization["organization_name"]

        if account_id_list is None:
            logger.debug(f"project_id={project_id}の、すべての労務管理情報を取得しています。")
            labor_list = self.service.wrapper.get_labor_control_worktime(
                project_id=project_id,
                organization_id=organization["organization_id"],
                from_date=start_date,
                to_date=end_date,
            )
        else:
            labor_list = []
            for account_id in account_id_list:
                logger.debug(f"project_id={project_id}の、ユーザ{len(account_id_list)}件分の労務管理情報を取得しています。")
                tmp_labor_list = self.service.wrapper.get_labor_control_worktime(
                    project_id=project_id, from_date=start_date, to_date=end_date, account_id=account_id
                )
                labor_list.extend(tmp_labor_list)

        # 労務管理情報の絞り込み
        labor_list = [e for e in labor_list if self.is_target_labor(e)]
        new_labor_list = []

        for labor in labor_list:
            member = self.facade.get_project_member_from_account_id(project_id, labor["account_id"])

            new_labor = self._get_labor_worktime(
                labor,
                member=member,
                project_title=project_title,
                organization_name=organization_name,
            )
            new_labor_list.append(new_labor)

        logger.debug(f"'{project_title}'プロジェクト('{project_id}')の労務管理情報の件数: {len(new_labor_list)}")
        return new_labor_list

    def get_account_id_list_from_project_id(self, user_id_list: List[str], project_id_list: List[str]) -> List[str]:
        """
        project_idのリストから、対象ユーザのaccount_id を取得する。

        Args:
            user_id_list:
            organization_name_list:

        Returns:
            account_idのリスト
        """
        account_id_list = []
        not_exists_user_id_list = []
        for user_id in user_id_list:
            member_exists = False
            for project_id in project_id_list:
                member = self.facade.get_project_member_from_user_id(project_id, user_id)
                if member is not None:
                    account_id_list.append(member["account_id"])
                    member_exists = True
                    break
            if not member_exists:
                not_exists_user_id_list.append(user_id)

        if len(not_exists_user_id_list) == 0:
            return account_id_list
        else:
            raise ValueError(f"以下のユーザは、指定されたプロジェクトのプロジェクトメンバではありませんでした。\n{not_exists_user_id_list}")

    def get_account_id_list_from_organization_name(
        self, user_id_list: List[str], organization_name_list: List[str]
    ) -> List[str]:
        """
        組織名のリストから、対象ユーザのaccount_id を取得する。

        Args:
            user_id_list:
            organization_name_list:

        Returns:
            account_idのリスト
        """

        def _get_account_id(fuser_id: str) -> Optional[str]:
            # 脱退した可能性のあるユーザの組織メンバ情報を取得する
            for organization_name in organization_name_list:
                member = self.service.wrapper.get_organization_member_or_none(organization_name, fuser_id)
                if member is not None:
                    return member["account_id"]
            return None

        # 組織メンバの一覧をする（ただし脱退したメンバは取得できない）
        all_organization_member_list = []
        for organization_name in organization_name_list:
            all_organization_member_list.extend(self.service.wrapper.get_all_organization_members(organization_name))

        user_id_dict = {e["user_id"]: e["account_id"] for e in all_organization_member_list}
        account_id_list = []
        not_exists_user_id_list = []
        for user_id in user_id_list:
            if user_id in user_id_dict:
                account_id_list.append(user_id_dict[user_id])
            else:
                account_id = _get_account_id(user_id)
                if account_id is not None:
                    account_id_list.append(account_id)
                else:
                    not_exists_user_id_list.append(user_id)

        if len(not_exists_user_id_list) == 0:
            return account_id_list
        else:
            raise ValueError(f"以下のユーザは、指定された組織の組織メンバではありませんでした。\n{not_exists_user_id_list}")

    def get_labor_worktime_list(
        self,
        *,
        organization_name_list: Optional[List[str]],
        project_id_list: Optional[List[str]],
        start_date: str,
        end_date: str,
        user_id_list: Optional[List[str]],
        account_id_list: Optional[List[str]],
    ) -> List[LaborWorktime]:

        labor_list: List[LaborWorktime] = []

        logger.info(f"労務管理情報を取得します。")
        if project_id_list is not None:
            if user_id_list is not None:
                account_id_list = self.get_account_id_list_from_project_id(
                    user_id_list, project_id_list=project_id_list
                )

            for project_id in project_id_list:
                labor_list.extend(
                    self.get_labor_list_from_project_id(
                        project_id,
                        account_id_list=account_id_list,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )

        elif organization_name_list is not None:
            if user_id_list is not None:
                account_id_list = self.get_account_id_list_from_organization_name(
                    user_id_list, organization_name_list=organization_name_list
                )
            for organization_name in organization_name_list:
                labor_list.extend(
                    self.get_labor_list_from_organization_name(
                        organization_name=organization_name,
                        account_id_list=account_id_list,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )

        else:
            raise RuntimeError(f"organization_name_list or project_id_list を指定してください。")

        return labor_list


class ListLaborWorktime(AbstractCommandLineInterface):
    def main(self) -> None:
        args = self.args

        arg_user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
        arg_account_id_list = get_list_from_args(args.account_id) if args.account_id is not None else None
        project_id_list = get_list_from_args(args.project_id) if args.project_id is not None else None
        organization_name_list = get_list_from_args(args.organization) if args.organization is not None else None

        target_columns = {TargetColumn(e) for e in args.columns}
        main_obj = ListLaborWorktimeMain(self.service, target_columns=target_columns)
        labor_worktime_list = main_obj.get_labor_worktime_list(
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            start_date=args.start_date,
            end_date=args.end_date,
            user_id_list=arg_user_id_list,
            account_id_list=arg_account_id_list,
        )

        if len(labor_worktime_list) > 0:
            df = pandas.DataFrame(labor_worktime_list)
            columns = BASE_COLUMNS + args.columns
            self.print_csv(df[columns])
        else:
            logger.info(f"労務管理一覧が0件のため、出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListLaborWorktime(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "-org",
        "--organization",
        type=str,
        nargs="+",
        help="集計対象の組織名を指定してください。`file://`を先頭に付けると、組織名の一覧が記載されたファイルを指定できます。",
    )

    target_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="集計対象のプロジェクトを指定してください。`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    user_group = parser.add_mutually_exclusive_group()
    user_group.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="集計対象のユーザのuser_idを指定してください。" "`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )
    user_group.add_argument(
        "--account_id",
        type=str,
        nargs="+",
        help="集計対象のユーザのaccount_idを指定してください。" "`file://`を先頭に付けると、account_id の一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--start_date", type=str, required=True, help="集計期間の開始日(YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, required=True, help="集計期間の終了日(YYYY-MM-DD)")

    parser.add_argument("-o", "--output", type=str, required=True, help="出力先ファイルのパス")

    parser.add_argument(
        "--columns",
        type=str,
        nargs="+",
        choices=[TargetColumn.ACTUAL_WORKTIME_HOUR.value, TargetColumn.PLAN_WORKTIME_HOUR.value],
        default=[TargetColumn.ACTUAL_WORKTIME_HOUR.value, TargetColumn.PLAN_WORKTIME_HOUR.value],
        help="出力する作業時間の列名",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_worktime"
    subcommand_help = "作業時間の一覧のCSVを出力します。"
    description = "作業時間の一覧のCSVを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
