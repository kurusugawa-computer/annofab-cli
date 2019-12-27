# flake8: noqa
#  type: ignore
# pylint: skip-file
import argparse
import datetime
import logging
from typing import Any, Dict, List, Tuple

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.experimental.utils import date_range, print_time_list_from_work_time_list
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, annofab_service: annofabapi.Resource, project_id: str, organization_id: str):
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.organization_id = organization_id

    def get_labor_control(self) -> List[Dict[str, Any]]:
        labor_control_df = self.annofab_service.api.get_labor_control(
            {"organization_id": self.organization_id, "project_id": self.project_id}
        )[0]
        return labor_control_df

    def get_account_statistics(self) -> List[Dict[str, Any]]:
        account_statistics = self.annofab_service.api.get_account_statistics(self.project_id)[0]
        return account_statistics

    def get_project_members(self) -> dict:
        project_members = self.annofab_service.api.get_project_members(project_id=self.project_id)[0]
        return project_members["list"]


class FutureTable(Table):
    def __init__(self, database: Database, task_query_param=None, user_id_list: List[str] = None):
        super().__init__(database, task_query_param)
        self.database = database
        self.user_id_search_list = [user_id.upper() for user_id in user_id_list]

    def create_labor_control_df(self):

        labor_control = self.database.get_labor_control()
        labor_control_list = []
        for l in labor_control:
            if l["values"] is None or l["values"]["working_time_by_user"] is None:
                aw_plans = 0.0
                aw_results = 0.0
            else:
                if l["values"]["working_time_by_user"]["plans"] is None:
                    aw_plans = 0.0
                else:
                    aw_plans = int(l["values"]["working_time_by_user"]["plans"]) / 60000
                if l["values"]["working_time_by_user"]["results"] is None:
                    aw_results = 0.0
                else:
                    aw_results = int(l["values"]["working_time_by_user"]["results"]) / 60000

            if l["account_id"] == None:
                continue
            if self.user_id_search_list == None:
                labor_control_list.append(
                    {
                        "account_id": l["account_id"],
                        "date": l["date"],
                        "aw_plans": aw_plans,
                        "aw_results": aw_results,
                        "username": self._get_username(l["account_id"]),
                        "af_time": 0.0,
                    }
                )
            else:
                user_id_bool_list = [
                    user_id_search in self._get_user_id(l["account_id"]).upper()
                    for user_id_search in self.user_id_search_list
                ]
                if True in user_id_bool_list:
                    labor_control_list.append(
                        {
                            "account_id": l["account_id"],
                            "date": l["date"],
                            "aw_plans": aw_plans,
                            "aw_results": aw_results,
                            "username": self._get_username(l["account_id"]),
                            "af_time": 0.0,
                        }
                    )

        return labor_control_list

    def create_account_statistics_df(self):
        """
        メンバごと、日ごとの作業時間
        """
        account_statistics = self.database.get_account_statistics()
        all_histories = []
        for account_info in account_statistics:

            account_id = account_info["account_id"]
            histories = account_info["histories"]
            if account_id == None:
                continue
            elif self.user_id_search_list == None:
                for history in histories:
                    history["af_time"] = annofabcli.utils.isoduration_to_minute(history["worktime"])
                    history["account_id"] = account_id
                    history["username"] = self._get_username(account_id)
                    history["aw_plans"] = 0.0
                    history["aw_results"] = 0.0

                all_histories.extend(histories)
            else:
                user_id_bool_list = [
                    user_id_search in self._get_user_id(account_id).upper().upper()
                    for user_id_search in self.user_id_search_list
                ]
                if True in user_id_bool_list:
                    for history in histories:
                        history["af_time"] = annofabcli.utils.isoduration_to_minute(history["worktime"])
                        history["account_id"] = account_id
                        history["username"] = self._get_username(account_id)
                        history["aw_plans"] = 0.0
                        history["aw_results"] = 0.0

                    all_histories.extend(histories)

        return all_histories

    def create_afaw_time_df(self) -> Tuple[List[Any], List[Any]]:

        account_statistics_df = self.create_account_statistics_df()
        labor_control_df = self.create_labor_control_df()
        username_list = []

        for labor_control in labor_control_df:
            for account_statistics in account_statistics_df:
                if (
                    account_statistics["account_id"] == labor_control["account_id"]
                    and account_statistics["date"] == labor_control["date"]
                ):
                    labor_control["af_time"] = account_statistics["af_time"]
                    labor_control["username"] = account_statistics["username"]
                    if not account_statistics["username"] in username_list:
                        username_list.append(account_statistics["username"])

        return labor_control_df, username_list


def get_organization_id_from_project_id(annofab_service: annofabapi.Resource, project_id: str) -> str:
    """
    project_idからorganization_idを返す
    """
    organization, _ = annofab_service.api.get_organization_of_project(project_id)
    return organization["organization_id"]


class ListLaborWorktime(AbstractCommandLineInterface):
    """
    労務管理画面の作業時間を出力する
    """

    def list_labor_worktime(self, project_id: str, user_id_list: List[str]):
        """
        """

        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])
        # プロジェクト or 組織に対して、必要な権限が付与されているかを確認

        organization_id = get_organization_id_from_project_id(self.service, project_id)
        database = Database(self.service, project_id, organization_id)
        # Annofabから取得した情報に関するデータベースを取得するクラス
        table_obj = FutureTable(database=database, user_id_list=user_id_list)
        # Databaseから取得した情報を元にPandas DataFrameを生成するクラス
        #     チェックポイントファイルがあること前提
        return table_obj.create_afaw_time_df()

    def main(self):
        args = self.args
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        date_list = date_range(start_date, end_date)
        user_id_list = args.user_id

        afaw_time_list = []
        project_members_list = []
        for i, project_id in enumerate(args.project_id):
            logger.debug(f"{i + 1} 件目: project_id = {project_id}")
            afaw_time_df, project_members = self.list_labor_worktime(project_id, user_id_list)
            afaw_time_list.append(afaw_time_df)
            project_members_list.extend(project_members)
        print_time_list, print_total_time = print_time_list_from_work_time_list(
            list(set(project_members_list)), afaw_time_list, date_list
        )

        output_lines: List[str] = []
        output_lines.append(f"Start: , {start_date},  End: , {end_date}")
        output_lines.append("project_title: ," + ",".join([self.facade.get_project_title(p) for p in args.project_id]))
        output_lines.extend([",".join([str(cell) for cell in row]) for row in print_time_list])
        output_lines.append("total_aw_plans: ," + str(print_total_time["total_aw_plans"]))
        output_lines.append("total_aw_results: ," + str(print_total_time["total_aw_results"]))
        output_lines.append("total_af_time: ," + str(print_total_time["total_af_time"]))
        output_lines.append("total_diff: ," + str(print_total_time["total_diff"]))
        output_lines.append("total_diff_per: ," + str(print_total_time["total_diff_per"]))
        annofabcli.utils.output_string("\n".join(output_lines), args.output)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListLaborWorktime(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="集計対象のプロジェクトのproject_idを指定します。複数指定した場合は合計値を出力します。",
    )
    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        default=None,
        help="集計対象のユーザのuser_idに部分一致するものを集計します。" "指定しない場合は、プロジェクトメンバが指定されます。",
    )
    parser.add_argument("--start_date", type=str, required=True, help="集計開始日(%%Y-%%m-%%d)")
    parser.add_argument("--end_date", type=str, required=True, help="集計終了日(%%Y-%%m-%%d)")

    argument_parser.add_output(required=True)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_worktime"
    subcommand_help = "労務管理画面の作業時間を出力します。"
    description = "作業者ごとに、「作業者が入力した実績時間」と「AnnoFabが集計した作業時間」の差分を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
