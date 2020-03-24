import argparse
import calendar
import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import more_itertools
import pandas
from annofabapi.models import OrganizationMember, Project
from dataclasses_json import dataclass_json

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_list_from_args

logger = logging.getLogger(__name__)


def catch_exception(function: Callable[..., Any]) -> Callable[..., Any]:
    """
    Exceptionをキャッチしてログにstacktraceを出力する。
    """

    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.exception(e)

    return wrapped


@dataclass_json
@dataclass(frozen=True)
class LaborWorktime:
    """
    労務管理情報
    """

    date: str
    organization_id: str
    organization_name: str
    project_id: str
    project_title: str
    account_id: str
    user_id: str
    username: str
    worktime_plan_hour: float
    worktime_result_hour: float


@dataclass_json
@dataclass(frozen=True)
class LaborAvailability:
    """
    労務管理情報
    """

    date: str
    account_id: str
    user_id: str
    username: str
    availability_hour: float


@dataclass_json
@dataclass(frozen=True)
class SumLaborWorktime:
    """
    出力用の作業時間情報
    """

    date: str
    user_id: str
    worktime_plan_hour: float
    worktime_result_hour: float


class ListWorktimeByUser(AbstractCommandLineInterface):
    """
    作業時間をユーザごとに出力する。
    """

    DATE_FORMAT = "%Y-%m-%d"
    MONTH_FORMAT = "%Y-%m"

    @staticmethod
    def create_required_columns(df, prior_columns):
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        return all_columns

    @staticmethod
    def get_member_from_user_id(
        organization_member_list: List[OrganizationMember], user_id: str
    ) -> Optional[OrganizationMember]:
        member = more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def get_member_from_account_id(
        organization_member_list: List[OrganizationMember], account_id: str
    ) -> Optional[OrganizationMember]:
        member = more_itertools.first_true(organization_member_list, pred=lambda e: e["account_id"] == account_id)
        return member

    @staticmethod
    def get_project_title(project_list: List[Project], project_id: str) -> str:
        project = more_itertools.first_true(project_list, pred=lambda e: e["project_id"] == project_id)
        if project is not None:
            return project["title"]
        else:
            return ""

    @staticmethod
    def get_worktime_hour(working_time_by_user: Optional[Dict[str, Any]], key: str) -> float:
        if working_time_by_user is None:
            return 0

        value = working_time_by_user.get(key)
        if value is None:
            return 0
        else:
            return value / 3600 / 1000

    def _get_labor_worktime(
        self, labor: Dict[str, Any], member: Optional[OrganizationMember], project_title: str, organization_name: str
    ) -> LaborWorktime:
        new_labor = LaborWorktime(
            date=labor["date"],
            organization_id=labor["organization_id"],
            organization_name=organization_name,
            project_id=labor["project_id"],
            project_title=project_title,
            account_id=labor["account_id"],
            user_id=member["user_id"] if member is not None else labor["account_id"],
            username=member["username"] if member is not None else labor["account_id"],
            worktime_plan_hour=self.get_worktime_hour(labor["values"]["working_time_by_user"], "plans"),
            worktime_result_hour=self.get_worktime_hour(labor["values"]["working_time_by_user"], "results"),
        )
        return new_labor

    def _get_labor_availability(self, labor: Dict[str, Any], member: Optional[OrganizationMember]) -> LaborAvailability:
        new_labor = LaborAvailability(
            date=labor["date"],
            account_id=labor["account_id"],
            user_id=member["user_id"] if member is not None else labor["account_id"],
            username=member["username"] if member is not None else labor["account_id"],
            availability_hour=self.get_worktime_hour(labor["values"]["working_time_by_user"], "plans"),
        )
        return new_labor

    def get_labor_availability_list_dict(
        self, user_id_list: List[str], start_date: str, end_date: str, member_list: List[OrganizationMember],
    ) -> Dict[str, List[LaborAvailability]]:
        """
        予定稼働時間を取得する
        Args:
            member_list:
            start_date:
            end_date:

        Returns:

        """
        labor_availability_dict = {}
        for user_id in user_id_list:
            # 予定稼働時間を取得するには、特殊な組織IDを渡す
            labor_list, _ = self.service.api.get_labor_control(
                {"organization_id": "___plannedWorktime___", "from": start_date, "to": end_date, "user_id": user_id}
            )
            new_labor_list = []
            for labor in labor_list:
                member = self.get_member_from_account_id(member_list, labor["account_id"])
                new_labor = self._get_labor_availability(labor, member=member)
                new_labor_list.append(new_labor)
            labor_availability_dict[user_id] = new_labor_list
        return labor_availability_dict

    def get_labor_list_from_project_id(
        self, project_id: str, member_list: List[OrganizationMember], start_date: Optional[str], end_date: Optional[str]
    ) -> List[LaborWorktime]:
        organization, _ = self.service.api.get_organization_of_project(project_id)
        organization_name = organization["organization_name"]

        labor_list, _ = self.service.api.get_labor_control(
            {
                "project_id": project_id,
                "organization_id": organization["organization_id"],
                "from": start_date,
                "to": end_date,
            }
        )
        project_title = self.service.api.get_project(project_id)[0]["title"]

        logger.info(f"'{project_title}'プロジェクト('{project_id}')の労務管理情報の件数: {len(labor_list)}")

        new_labor_list = []
        for labor in labor_list:
            # 個人に紐付かないデータの場合
            if labor["account_id"] is None:
                continue

            member = self.get_member_from_account_id(member_list, labor["account_id"])
            new_labor = self._get_labor_worktime(
                labor, member=member, project_title=project_title, organization_name=organization_name
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    def get_labor_list_from_organization_name(
        self,
        organization_name: str,
        member_list: List[OrganizationMember],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[LaborWorktime]:
        organization, _ = self.service.api.get_organization(organization_name)
        organization_id = organization["organization_id"]
        project_list = self.service.wrapper.get_all_projects_of_organization(organization_name)

        labor_list, _ = self.service.api.get_labor_control(
            {"organization_id": organization_id, "from": start_date, "to": end_date}
        )
        logger.info(f"'{organization_name}'組織の労務管理情報の件数: {len(labor_list)}")
        new_labor_list = []
        for labor in labor_list:
            member = self.get_member_from_account_id(member_list, labor["account_id"])
            project_title = self.get_project_title(project_list, labor["project_id"])
            new_labor = self._get_labor_worktime(
                labor, member=member, project_title=project_title, organization_name=organization_name
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    @staticmethod
    def get_sum_worktime_list(
        labor_list: List[LaborWorktime], user_id: str, start_date: str, end_date: str
    ) -> List[SumLaborWorktime]:
        sum_labor_list = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUser.DATE_FORMAT)
            filtered_list = [e for e in labor_list if e.user_id == user_id and e.date == str_date]
            worktime_plan_hour = sum([e.worktime_plan_hour for e in filtered_list])
            worktime_result_hour = sum([e.worktime_result_hour for e in filtered_list])

            labor = SumLaborWorktime(
                user_id=user_id,
                date=date,
                worktime_plan_hour=worktime_plan_hour,
                worktime_result_hour=worktime_result_hour,
            )
            sum_labor_list.append(labor)

        return sum_labor_list

    @staticmethod
    def write_sum_worktime_list(sum_worktime_df: pandas.DataFrame, output_dir: Path):
        sum_worktime_df.round(3).to_csv(str(output_dir / "ユーザごとの作業時間.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    def write_sum_plan_worktime_list(sum_worktime_df: pandas.DataFrame, output_dir: Path) -> None:
        """
        出勤予定かどうかを判断するため、作業予定時間が"0"のときは"☓",　そうでないときは"○"で出力する
        Args:
            sum_worktime_df:
            output_dir:

        """

        def create_mark(value) -> str:
            if value == 0:
                return "×"
            else:
                return "○"

        def is_plan_column(c) -> bool:
            c1, c2 = c
            if c1 in ["date", "dayofweek"]:
                return False
            return c2 == "作業予定"

        username_list = [e[0] for e in sum_worktime_df.columns if is_plan_column(e)]

        for username in username_list:
            # SettingWithCopyWarning を避けるため、暫定的に値をコピーする
            sum_worktime_df[(username, "作業予定_記号")] = sum_worktime_df[(username, "作業予定")].map(create_mark)

        output_columns = [("date", ""), ("dayofweek", "")] + [(e, "作業予定_記号") for e in username_list]
        sum_worktime_df[output_columns].to_csv(str(output_dir / "ユーザごとの作業予定_記号.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    def write_worktime_list(worktime_df: pandas.DataFrame, output_dir: Path):
        worktime_df = worktime_df.rename(
            columns={"worktime_plan_hour": "作業予定時間", "worktime_result_hour": "作業実績時間"}
        ).round(3)
        columns = [
            "date",
            "organization_name",
            "project_title",
            "project_id",
            "username",
            "user_id",
            "作業予定時間",
            "作業実績時間",
        ]
        worktime_df[columns].to_csv(str(output_dir / "作業時間の詳細一覧.csv"), encoding="utf_8_sig", index=False)

    def get_organization_member_list(
        self, organization_name_list: Optional[List[str]], project_id_list: Optional[List[str]]
    ) -> List[OrganizationMember]:
        member_list: List[OrganizationMember] = []

        if project_id_list is not None:
            tmp_organization_name_list = []
            for project_id in project_id_list:
                organization, _ = self.service.api.get_organization_of_project(project_id)
                tmp_organization_name_list.append(organization["organization_name"])

            organization_name_list = list(set(tmp_organization_name_list))

        if organization_name_list is not None:
            for organization_name in organization_name_list:
                member_list.extend(self.service.wrapper.get_all_organization_members(organization_name))

        return member_list

    def get_availability_list(
        self, labor_availability_list: List[LaborAvailability], start_date: str, end_date: str,
    ) -> List[Optional[float]]:
        availability_list: List[Optional[float]] = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUser.DATE_FORMAT)
            labor = more_itertools.first_true(labor_availability_list, pred=lambda e: e.date == str_date)
            if labor is not None:
                availability_list.append(labor.availability_hour)
            else:
                availability_list.append(None)

        return availability_list

    def get_labor_list(
        self,
        member_list: List[OrganizationMember],
        organization_name_list: Optional[List[str]],
        project_id_list: Optional[List[str]],
        user_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[LaborWorktime]:

        labor_list: List[LaborWorktime] = []

        logger.info(f"労務管理情報を取得します。")
        if project_id_list is not None:
            for project_id in project_id_list:
                labor_list.extend(
                    self.get_labor_list_from_project_id(
                        project_id, member_list=member_list, start_date=start_date, end_date=end_date
                    )
                )

        elif organization_name_list is not None:
            for organization_name in organization_name_list:
                labor_list.extend(
                    self.get_labor_list_from_organization_name(
                        organization_name, member_list=member_list, start_date=start_date, end_date=end_date
                    )
                )

        else:
            raise RuntimeError(f"organization_name_list or project_id_list を指定してください。")

        # 集計対象ユーザで絞り込む
        if user_id_list is not None:
            return [e for e in labor_list if e.user_id in user_id_list]
        else:
            return labor_list

    def write_labor_list(
        self,
        labor_list: List[LaborWorktime],
        member_list: List[OrganizationMember],
        user_id_list: List[str],
        start_date: str,
        end_date: str,
        output_dir: Path,
        labor_availability_list_dict: Optional[Dict[str, List[LaborAvailability]]] = None,
    ):

        reform_dict = {
            ("date", ""): [
                e.strftime(ListWorktimeByUser.DATE_FORMAT) for e in pandas.date_range(start=start_date, end=end_date)
            ],
            ("dayofweek", ""): [e.strftime("%a") for e in pandas.date_range(start=start_date, end=end_date)],
        }

        for user_id in user_id_list:
            sum_worktime_list = self.get_sum_worktime_list(
                labor_list, user_id=user_id, start_date=start_date, end_date=end_date
            )
            member = self.get_member_from_user_id(member_list, user_id)
            if member is not None:
                username = member["username"]
            else:
                logger.warning(f"user_idが'{user_id}'のユーザは存在しません。")
                username = user_id

            reform_dict.update(
                {
                    (username, "作業予定"): [e.worktime_plan_hour for e in sum_worktime_list],
                    (username, "作業実績"): [e.worktime_result_hour for e in sum_worktime_list],
                }
            )

            if labor_availability_list_dict is not None:
                labor_availability_list = labor_availability_list_dict[user_id]
                reform_dict.update(
                    {(username, "予定稼働"): self.get_availability_list(labor_availability_list, start_date, end_date),}
                )

        sum_worktime_df = pandas.DataFrame(reform_dict)
        catch_exception(self.write_sum_worktime_list)(sum_worktime_df, output_dir)

        catch_exception(self.write_sum_plan_worktime_list)(sum_worktime_df, output_dir)

        worktime_df = pandas.DataFrame([e.to_dict() for e in labor_list])  # type: ignore
        catch_exception(self.write_worktime_list)(worktime_df, output_dir)

    def print_labor_worktime_list(
        self,
        organization_name_list: Optional[List[str]],
        project_id_list: Optional[List[str]],
        user_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
        output_dir: Path,
        add_availability: bool = False,
    ) -> None:
        """
        作業時間の一覧を出力する
        """
        member_list = self.get_organization_member_list(organization_name_list, project_id_list)

        labor_list = self.get_labor_list(
            member_list=member_list,
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            user_id_list=user_id_list,
            start_date=start_date,
            end_date=end_date,
        )

        if len(labor_list) == 0:
            logger.warning(f"労務管理情報が0件のため、作業時間の詳細一覧.csv は出力しません。")
            return

        if start_date is None or end_date is None:
            sorted_labor_list = sorted(labor_list, key=lambda e: e.date)
            if start_date is None:
                start_date = sorted_labor_list[0].date
            if end_date is None:
                end_date = sorted_labor_list[-1].date

        logger.info(f"集計期間: start_date={start_date}, end_date={end_date}")

        if user_id_list is None:
            tmp_user_id_list = list({e.user_id for e in labor_list})
            logger.debug(tmp_user_id_list)
            user_id_list = sorted(tmp_user_id_list)
        logger.info(f"集計対象ユーザの数: {len(user_id_list)}")

        if project_id_list is None:
            project_id_list = sorted(list({e.project_id for e in labor_list}))
        logger.info(f"集計対象プロジェクトの数: {len(project_id_list)}")

        labor_availability_list_dict = None
        if add_availability:
            labor_availability_list_dict = self.get_labor_availability_list_dict(
                user_id_list=user_id_list, start_date=start_date, end_date=end_date, member_list=member_list,
            )

        self.write_labor_list(
            labor_list=labor_list,
            member_list=member_list,
            user_id_list=user_id_list,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            labor_availability_list_dict=labor_availability_list_dict,
        )

    def get_user_id_list_from_project_id_list(self, project_id_list: List[str]) -> List[str]:
        """
        プロジェクトメンバ一覧からuser_id_listを取得する。
        Args:
            project_id_list:

        Returns:
            user_id_list

        """
        member_list: List[Dict[str, Any]] = []
        for project_id in project_id_list:
            member_list.extend(self.service.wrapper.get_all_project_members(project_id))
        user_id_list = [e["user_id"] for e in member_list]
        return list(set(user_id_list))

    @staticmethod
    def get_first_and_last_date(str_month: str) -> Tuple[str, str]:
        """
        年月（"YYYY-MM"）から、月初と月末の日付を返す。

        Args:
            str_month: 年月（"YYYY-MM"）

        Returns:
            月初と月末の日付が格納されたタプル

        """
        dt_first_date = datetime.datetime.strptime(str_month, ListWorktimeByUser.MONTH_FORMAT)
        _, days = calendar.monthrange(dt_first_date.year, dt_first_date.month)
        dt_last_date = dt_first_date + datetime.timedelta(days=(days - 1))
        return (
            dt_first_date.strftime(ListWorktimeByUser.DATE_FORMAT),
            dt_last_date.strftime(ListWorktimeByUser.DATE_FORMAT),
        )

    @staticmethod
    def get_start_and_end_date_from_month(start_month: str, end_month: str) -> Tuple[str, str]:
        """
        開始月、終了月から、開始日付、終了日付を取得する。

        Args:
            start_month:
            end_month:

        Returns:


        """
        first_date, _ = ListWorktimeByUser.get_first_and_last_date(start_month)
        _, end_date = ListWorktimeByUser.get_first_and_last_date(end_month)
        return first_date, end_date

    @staticmethod
    def get_start_and_end_date_from_args(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
        if args.start_date is not None:
            start_date = args.start_date
        elif args.start_month is not None:
            start_date, _ = ListWorktimeByUser.get_first_and_last_date(args.start_month)
        else:
            start_date = None

        if args.end_date is not None:
            end_date = args.end_date
        elif args.end_month is not None:
            _, end_date = ListWorktimeByUser.get_first_and_last_date(args.end_month)
        else:
            end_date = None

        return (start_date, end_date)

    def main(self) -> None:
        args = self.args

        arg_user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
        project_id_list = get_list_from_args(args.project_id) if args.project_id is not None else None
        organization_name_list = get_list_from_args(args.organization) if args.organization is not None else None

        start_date, end_date = self.get_start_and_end_date_from_args(args)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        self.print_labor_worktime_list(
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            user_id_list=arg_user_id_list,
            availability=args.availability,
        )  # type: ignore


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeByUser(service, facade, args).main()


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

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="集計対象のユーザのuser_idを指定してください。`--organization`を指定した場合は必須です。"
        "指定しない場合は、プロジェクトメンバが指定されます。"
        "`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--availability", action="store_true", help="指定した場合、予定稼働時間も出力します。")

    start_period_group = parser.add_mutually_exclusive_group()
    start_period_group.add_argument("--start_date", type=str, help="集計期間の開始日(YYYY-MM-DD)")
    start_period_group.add_argument("--start_month", type=str, help="集計期間の開始月(YYYY-MM-DD)")

    end_period_group = parser.add_mutually_exclusive_group()
    end_period_group.add_argument("--end_date", type=str, help="集計期間の終了日(YYYY-MM)")
    end_period_group.add_argument("--end_month", type=str, help="集計期間の終了月(YYYY-MM)")

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力先のディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_worktime_by_user"
    subcommand_help = "ユーザごとに作業予定時間、作業実績時間を出力します。"
    description = "ユーザごとに作業予定時間、作業実績時間を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
