import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import more_itertools
import pandas
from annofabapi.models import OrganizationMember, Project
from dataclasses_json import dataclass_json

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_list_from_args

logger = logging.getLogger(__name__)


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

    @staticmethod
    def create_required_columns(df, prior_columns):
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        return all_columns

    @staticmethod
    def get_member_from_user_id(organization_member_list: List[OrganizationMember],
                                user_id: str) -> Optional[OrganizationMember]:
        member = more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def get_member_from_account_id(organization_member_list: List[OrganizationMember],
                                   account_id: str) -> Optional[OrganizationMember]:
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
    def get_worktime_hour(working_time_by_user: Dict[str, Any], key: str) -> float:
        value = working_time_by_user.get(key)
        if value is None:
            return 0
        else:
            return value / 3600 / 1000

    def get_labor_list(self, organization_name: str, start_date: str, end_date: str) -> List[LaborWorktime]:
        new_labor_list = []
        organization, _ = self.service.api.get_organization(organization_name)
        organization_id = organization["organization_id"]
        organization_member_list = self.service.wrapper.get_all_organization_members(organization_name)
        project_list = self.service.wrapper.get_all_projects_of_organization(organization_name)

        labor_list, _ = self.service.api.get_labor_control({
            "organization_id": organization_id,
            "from": start_date,
            "to": end_date
        })
        logger.info(f"'{organization_name}'組織の労務管理情報の件数: {len(labor_list)}")
        for labor in labor_list:
            member = self.get_member_from_account_id(organization_member_list, labor["account_id"])
            new_labor = LaborWorktime(
                date=labor["date"],
                organization_id=labor["organization_id"],
                organization_name=organization_name,
                project_id=labor["project_id"],
                project_title=self.get_project_title(project_list, labor["project_id"]),
                account_id=labor["account_id"],
                user_id=member["user_id"] if member is not None else "",
                username=member["username"] if member is not None else "",
                worktime_plan_hour=self.get_worktime_hour(labor["values"]["working_time_by_user"], "plans"),
                worktime_result_hour=self.get_worktime_hour(labor["values"]["working_time_by_user"], "results"),
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    @staticmethod
    def get_sum_worktime_list(labor_list: List[LaborWorktime], user_id: str, start_date: str,
                              end_date: str) -> List[SumLaborWorktime]:
        sum_labor_list = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUser.DATE_FORMAT)
            filtered_list = [e for e in labor_list if e.user_id == user_id and e.date == str_date]
            worktime_plan_hour = sum([e.worktime_plan_hour for e in filtered_list])
            worktime_result_hour = sum([e.worktime_result_hour for e in filtered_list])

            labor = SumLaborWorktime(user_id=user_id, date=date, worktime_plan_hour=worktime_plan_hour,
                                     worktime_result_hour=worktime_result_hour)
            sum_labor_list.append(labor)

        return sum_labor_list

    @staticmethod
    def write_sum_worktime_list(sum_worktime_df: pandas.DataFrame, output_dir: Path):
        sum_worktime_df.to_csv(str(output_dir / "ユーザごとの作業時間.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    def write_worktime_list(worktime_df: pandas.DataFrame, output_dir: Path):
        worktime_df = worktime_df.rename(columns={"worktime_plan_hour": "作業予定時間", "worktime_result_hour": "作業実績時間"})
        columns = ListWorktimeByUser.create_required_columns(
            worktime_df, ["date", "organization_name", "project_title", "username", "作業予定時間", "作業実績時間"])
        worktime_df[columns].to_csv(str(output_dir / "作業時間の詳細一覧.csv"), encoding="utf_8_sig", index=False)

    def print_labor_worktime_list(self, organization_name_list: List[str], user_id_list: List[str], start_date: str,
                                  end_date: str, output_dir: Path) -> None:
        """
        作業時間の一覧を出力する
        """
        labor_list = []
        member_list: List[OrganizationMember] = []
        for organization_name in organization_name_list:
            labor_list.extend(self.get_labor_list(organization_name, start_date=start_date, end_date=end_date))
            member_list.extend(self.service.wrapper.get_all_organization_members(organization_name))

        reform_dict = {
            ("date", ""): [
                e.strftime(ListWorktimeByUser.DATE_FORMAT) for e in pandas.date_range(start=start_date, end=end_date)
            ],
            ("dayofweek", ""): [e.strftime("%a") for e in pandas.date_range(start=start_date, end=end_date)],
        }

        for user_id in user_id_list:
            sum_worktime_list = self.get_sum_worktime_list(labor_list, user_id=user_id, start_date=start_date,
                                                           end_date=end_date)
            member = self.get_member_from_user_id(member_list, user_id)
            if member is not None:
                username = member["username"]
            else:
                logger.warning(f"user_idが'{user_id}'のユーザは存在しません。")
                username = user_id

            reform_dict.update({
                (username, "作業予定"): [e.worktime_plan_hour for e in sum_worktime_list],
                (username, "作業実績"): [e.worktime_result_hour for e in sum_worktime_list]
            })

        sum_worktime_df = pandas.DataFrame(reform_dict)
        self.write_sum_worktime_list(sum_worktime_df, output_dir)

        worktime_df = pandas.DataFrame([e.to_dict() for e in labor_list])  # type: ignore
        self.write_worktime_list(worktime_df, output_dir)

    def main(self):
        args = self.args
        user_id_list = get_list_from_args(args.user_id)
        organization_name_list = get_list_from_args(args.organization)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        self.print_labor_worktime_list(organization_name_list=organization_name_list, user_id_list=user_id_list,
                                       start_date=args.start_date, end_date=args.end_date, output_dir=output_dir)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListWorktimeByUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument('-org', '--organization', type=str, nargs='+', required=True,
                        help='集計対象の組織名を指定してください。`file://`を先頭に付けると、組織名の一覧が記載されたファイルを指定できます。')

    parser.add_argument('-u', '--user_id', type=str, nargs='+', required=True,
                        help='集計対象のユーザのuser_idを指定してください。`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。')

    parser.add_argument("--start_date", type=str, required=True, help="集計期間の開始日(%%Y-%%m-%%d)")
    parser.add_argument("--end_date", type=str, required=True, help="集計期間の終了日(%%Y-%%m-%%d)")

    parser.add_argument('-o', '--output_dir', type=str, required=True, help='出力先のディレクトリのパス')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_worktime_by_user"
    subcommand_help = "ユーザごとに作業時間を出力します。"
    description = ("ユーザごとに作業時間を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
