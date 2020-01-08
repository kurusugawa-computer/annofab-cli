import argparse
import datetime
import logging
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
import pandas as pd
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.experimental.utils import add_id_csv, print_time_list_from_work_time_list

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


class Table:
    def __init__(self, database: Database, facade: AnnofabApiFacade):
        self.database = database
        self.project_id = database.project_id
        self.facade = facade

    def create_labor_control_df(self):

        labor_control = self.database.get_labor_control()
        labor_control_list = []
        for l in labor_control:

            if l["account_id"] is not None:
                new_history = {
                    "user_name": self._get_username(l["account_id"]),
                    "user_id": self._get_user_id(l["account_id"]),
                    "project_id": self.project_id,
                    "date": l["date"],
                    "aw_plans": None
                    if l["values"]["working_time_by_user"]["plans"] is None
                    else int(l["values"]["working_time_by_user"]["plans"]) / 60000,
                    "aw_results": None
                    if l["values"]["working_time_by_user"]["results"] is None
                    else int(l["values"]["working_time_by_user"]["results"]) / 60000,
                }
                labor_control_list.append(new_history)

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
            if account_id is not None:
                for history in histories:
                    new_history = {
                        "user_name": self._get_username(account_id),
                        "user_id": self._get_user_id(account_id),
                        "project_id": self.project_id,
                        "date": history["date"],
                        "af_time": annofabcli.utils.isoduration_to_minute(history["worktime"]),
                    }
                    all_histories.append(new_history)

        return all_histories

    def create_afaw_time_df(self) -> pd.DataFrame:

        account_statistics_df = pd.DataFrame(self.create_account_statistics_df())
        labor_control_df = pd.DataFrame(self.create_labor_control_df())
        df = pd.merge(account_statistics_df, labor_control_df, on=["user_name", "user_id", "project_id", "date"])
        return df

    def _get_user_id(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのuser_idを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.facade.get_organization_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["user_id"]
        else:
            return account_id

    def _get_username(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.facade.get_organization_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id


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

    def list_labor_worktime(self, project_id: str):
        """
        """

        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])
        # プロジェクト or 組織に対して、必要な権限が付与されているかを確認

        organization_id = get_organization_id_from_project_id(self.service, project_id)
        database = Database(self.service, project_id, organization_id)
        # Annofabから取得した情報に関するデータベースを取得するクラス
        table_obj = Table(database=database, facade=self.facade)
        # Databaseから取得した情報を元にPandas DataFrameを生成するクラス
        #     チェックポイントファイルがあること前提
        return table_obj.create_afaw_time_df()

    def main(self):
        args = self.args
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        user_id_list = args.user_id

        total_df = pd.DataFrame([])
        for i, project_id in enumerate(args.project_id):
            logger.debug(f"{i + 1} 件目: project_id = {project_id}")
            afaw_time_df = self.list_labor_worktime(project_id)
            del afaw_time_df["project_id"]
            total_df = pd.concat([total_df, afaw_time_df])
        df = print_time_list_from_work_time_list(user_id_list, total_df, start_date, end_date)

        df.to_csv(args.output, date_format="%Y-%m-%d")
        add_id_csv(args.output, args.project_id)


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
