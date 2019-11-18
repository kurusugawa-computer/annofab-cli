import argparse
import logging
from dataclasses import dataclass
from dataclasses_json import dataclass_json

from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import
import pandas
from annofabapi.models import SupplementaryData, OrganizationMember, Project

import more_itertools
import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login, \
    get_list_from_args
from annofabcli.common.enums import FormatArgument
import datetime

logger = logging.getLogger(__name__)


def str_to_datetime(d: str) -> datetime.datetime:
    """
    文字列 `YYYY-MM-DDD` をdatetime.datetimeに変換する。
    """
    return datetime.datetime.strptime(d, '%Y-%m-%d')


@dataclass_json
@dataclass(frozen=True)
class LaborWorktime:
    """
    出力用の作業時間情報
    """
    date: str
    organization_id: str
    organization_name: int
    project_id: str
    project_title: str
    account_id: str
    user_id: str
    username: str
    worktime_plan_hour: float
    worktime_result_hour: float


class ListWorktimeByUser(AbstractCommandLineInterface):
    DATE_FORMAT = "%Y-%m-%d"

    """
    作業時間をユーザごとに出力する。
    """

    @annofabcli.utils.allow_404_error
    def get_supplementary_data_list(self, project_id: str, input_data_id: str) -> SupplementaryData:
        supplementary_data_list, _ = self.service.api.get_supplementary_data_list(project_id, input_data_id)
        return supplementary_data_list

    def get_all_supplementary_data_list(self, project_id: str,
                                        input_data_id_list: List[str]) -> List[SupplementaryData]:
        """
        補助情報一覧を取得する。
        """
        all_supplementary_data_list: List[SupplementaryData] = []

        logger.debug(f"{len(input_data_id_list)}件の入力データに紐づく補助情報を取得します。")
        for index, input_data_id in enumerate(input_data_id_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index + 1} 件目の入力データを取得します。")

            supplementary_data_list = self.get_supplementary_data_list(project_id, input_data_id)
            if supplementary_data_list is not None:
                all_supplementary_data_list.extend(supplementary_data_list)
            else:
                logger.warning(f"入力データ '{input_data_id}' に紐づく補助情報が見つかりませんでした。")

        return all_supplementary_data_list

    @staticmethod
    def get_member_from_user_id(organization_member_list: List[OrganizationMember], user_id: str) -> Optional[
        OrganizationMember]:
        member = more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def get_member_from_account_id(organization_member_list: List[OrganizationMember], account_id: str) -> Optional[
        OrganizationMember]:
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

        labor_list = \
            self.service.api.get_labor_control(
                {"organization_id": organization_id, "from": start_date, "to": end_date})[0][
                "list"]
        for labor in labor_list:
            member = self.get_member_from_account_id(organization_member_list, labor["account_id"])

            new_labor = LaborWorktime(
                date=labor["date"],
                organization_id=labor["organization_id"],
                organization_name=labor["organization_name"],
                project_id=labor["project_id"],
                project_title=self.get_project_title(project_list, labor["project_id"]),
                account_id=labor["account_id"],
                user_id=member["user_id"] if member is not None else "",
                username=member["username"] if member is not None else "",
                worktime_plan_hour=self.get_worktime_hour(labor["working_time_by_user"], "plans"),
                worktime_result_hour=self.get_worktime_hour(labor["working_time_by_user"], "results"),
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    @staticmethod
    def get_sum_worktime_list(labor_list: List[LaborWorktime], user_id: str, start_date: str, end_date: str):
        sum_labor_list = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUser.DATE_FORMAT)
            filtered_list = [e for e in labor_list if e.user_id == user_id and e.date == str_date]
            worktime_plan_hour = sum([e["worktime_plan_hour"] for e in filtered_list])
            worktime_result_hour = sum([e["worktime_result_hour"] for e in filtered_list])

            labor = LaborWorktime(user_id=user_id, date=date, worktime_plan_hour=worktime_plan_hour, worktime_result_hour=worktime_result_hour)
            sum_labor_list.append(labor)

        return sum_labor_list

    def print_labor_worktime_list(self, organization_name_list: List[str], user_id_list: List[str], start_date: str,
                        end_date: str) -> None:
        """
        作業時間の一覧を出力する
        """
        labor_list = []
        for organization_name in organization_name_list:
            labor_list.extend(self.get_labor_list(organization_name, start_date=start_date, end_date=end_date))

        reform_dict = {
            ("date",):[e.strftime(ListWorktimeByUser.DATE_FORMAT) for e in pandas.date_range(start=start_date, end=end_date)],
            ("dayofweek",): [e.strftime("%a") for e in pandas.date_range(start=start_date, end=end_date)],
        }

        for user_id in user_id_list:
            sum_worktime_list = self.get_sum_worktime_list(labor_list, user_id=user_id, start_date=start_date, end_date=end_date)
            reform_dict.update({(user_id, "worktime_plan_hour"): [e.worktime_plan_hour for e in sum_worktime_list],
                                (user_id, "worktime_result_hour"): [e.worktime_result_hour for e in sum_worktime_list]})

        sum_worktime_df = pandas.DataFrame(reform_dict)
        self.print_csv(sum_worktime_df)

    def main(self):
        args = self.args
        user_id_list = get_list_from_args(args.user_id)
        organization_name_list = get_list_from_args(args.organization)
        self.print_labor_worktime_list(organization_name_list=organization_name_list, user_id_list=user_id_list, start_date=args.start_date, end_date=args.end_date)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListWorktimeByUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument('-org', '--organization', type=str, nargs='+', required=True,
                        help='集計対象の組織名を指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。')

    parser.add_argument('-u', '--user_id', type=str, nargs='+', required=True,
                        help='集計対象のユーザのuser_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。')

    parser.add_argument("--start_date", type=str, required=True, help="集計期間の開始日(%%Y-%%m-%%d)")
    parser.add_argument("--end_date", type=str, required=True, help="集計期間の終了日(%%Y-%%m-%%d)")

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_worktime_by_user"
    subcommand_help = "ユーザごとに作業時間を出力します。"
    description = ("ユーザごとに作業時間を出力します。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
