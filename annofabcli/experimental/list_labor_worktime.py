import argparse
import datetime
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
import numpy as np
import pandas as pd
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.experimental.utils import (
    FormatTarget,
    TimeUnitTarget,
    add_id_csv,
    create_column_list,
    create_column_list_per_project,
    print_byname_total_list,
    print_time_list_from_work_time_list,
    print_total,
    timeunit_conversion,
)

logger = logging.getLogger(__name__)


class Database:
    def __init__(
        self,
        annofab_service: annofabapi.Resource,
        project_id: str,
        organization_id: str,
        start_date: str,
        end_date: str,
    ):
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.organization_id = organization_id
        self.start_date = start_date
        self.end_date = end_date

    def get_labor_control(self) -> List[Dict[str, Any]]:
        labor_control_df = self.annofab_service.api.get_labor_control(
            {
                "organization_id": self.organization_id,
                "project_id": self.project_id,
                "from": self.start_date,
                "to": self.end_date,
            }
        )[0]
        return labor_control_df

    def get_account_statistics(self) -> List[Dict[str, Any]]:
        account_statistics = self.annofab_service.wrapper.get_account_statistics(self.project_id)
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
        for labor in labor_control:
            if labor["account_id"] is not None:
                new_history = {
                    "user_name": self._get_username(labor["account_id"]),
                    "user_id": self._get_user_id(labor["account_id"]),
                    "user_biography": self._get_user_biography(labor["account_id"]),
                    "date": labor["date"],
                    "worktime_planned": np.nan
                    if labor["values"]["working_time_by_user"]["plans"] is None
                    else int(labor["values"]["working_time_by_user"]["plans"]) / 60000,
                    "worktime_actual": np.nan
                    if labor["values"]["working_time_by_user"]["results"] is None
                    else int(labor["values"]["working_time_by_user"]["results"]) / 60000,
                    "working_description": labor["values"]["working_time_by_user"]["description"]
                    if labor["values"]["working_time_by_user"]["results"] is not None
                    else None,
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
                        "user_biography": self._get_user_biography(account_id),
                        "date": history["date"],
                        "worktime_monitored": annofabcli.utils.isoduration_to_minute(history["worktime"]),
                    }
                    all_histories.append(new_history)

        return all_histories

    def create_afaw_time_df(self) -> pd.DataFrame:
        account_statistics_df = pd.DataFrame(self.create_account_statistics_df())
        labor_control_df = pd.DataFrame(self.create_labor_control_df())
        if len(account_statistics_df) == 0 and len(labor_control_df) == 0:
            df = pd.DataFrame([])
        elif len(account_statistics_df) == 0:

            labor_control_df["worktime_monitored"] = np.nan
            df = labor_control_df
        elif len(labor_control_df) == 0:
            account_statistics_df["worktime_planned"] = np.nan
            account_statistics_df["worktime_actual"] = np.nan
            df = account_statistics_df
        else:
            df = pd.merge(
                account_statistics_df,
                labor_control_df,
                on=["user_name", "user_id", "date", "user_biography"],
                how="outer",
            )
        df["project_id"] = self.project_id
        df["project_title"] = self.facade.get_project_title(self.project_id)
        return df

    def _get_user_id(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのuser_idを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.facade.get_project_member_from_account_id(self.project_id, account_id)
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

        member = self.facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id

    def _get_user_biography(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのbiographyを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["biography"]
        else:
            return account_id


def get_organization_id_from_project_id(annofab_service: annofabapi.Resource, project_id: str) -> str:
    """
    project_idからorganization_idを返す
    """
    organization, _ = annofab_service.api.get_organization_of_project(project_id)
    return organization["organization_id"]


def refine_df(
    df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date, user_id_list: Optional[List[str]]
) -> pd.DataFrame:
    # 日付で絞り込み
    df["date"] = pd.to_datetime(df["date"]).dt.date
    refine_day_df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
    # user_id を絞り込み
    refine_user_df = (
        refine_day_df
        if user_id_list is None
        else refine_day_df[refine_day_df["user_id"].str.contains("|".join(user_id_list), case=False)].copy()
    )
    return refine_user_df


class ListLaborWorktime(AbstractCommandLineInterface):
    """
    労務管理画面の作業時間を出力する
    """

    def _get_project_title_list(self, project_id_list: List[str]) -> List[str]:
        return [self.facade.get_project_title(project_id) for project_id in project_id_list]

    def list_labor_worktime(self, project_id: str, start_date: str, end_date: str) -> pd.DataFrame:

        """"""

        super().validate_project(
            project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
        )
        # プロジェクト or 組織に対して、必要な権限が付与されているかを確認

        organization_id = get_organization_id_from_project_id(self.service, project_id)
        database = Database(self.service, project_id, organization_id, start_date, end_date=end_date)
        # Annofabから取得した情報に関するデータベースを取得するクラス
        table_obj = Table(database=database, facade=self.facade)
        # Databaseから取得した情報を元にPandas DataFrameを生成するクラス
        #     チェックポイントファイルがあること前提
        return table_obj.create_afaw_time_df()

    def _output(self, output: Any, df: pd.DataFrame, index: bool, add_project_id: bool, project_id_list: List[str]):
        if isinstance(output, str):
            Path(output).parent.mkdir(exist_ok=True, parents=True)
        df.to_csv(
            output,
            date_format="%Y-%m-%d",
            encoding="utf_8_sig",
            line_terminator="\r\n",
            float_format="%.2f",
            index=index,
        )
        if output != sys.stdout and add_project_id:
            add_id_csv(output, self._get_project_title_list(project_id_list))

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli experimental list_labor_worktime: error:"
        if args.start_date is not None and args.end_date is not None:
            if args.start_date > args.end_date:
                print(
                    f"{COMMON_MESSAGE} argument `START_DATE <= END_DATE` の関係を満たしていません。",
                    file=sys.stderr,
                )
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        format_target = FormatTarget(args.format)
        time_unit = TimeUnitTarget(args.time_unit)

        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

        total_df = pd.DataFrame([])

        # プロジェクトごとにデータを取得
        project_id_list = get_list_from_args(args.project_id)
        logger.info(f"{len(project_id_list)} 件のプロジェクトを取得します。")
        for i, project_id in enumerate(list(set(project_id_list))):
            logger.debug(f"{i + 1} 件目: project_id = {project_id}")
            try:
                afaw_time_df = self.list_labor_worktime(
                    project_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
                )
                total_df = pd.concat([total_df, afaw_time_df], sort=True)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(e)
                logger.error(f"プロジェクトにアクセスできませんでした（project_id={project_id} ）。")

        # データが無い場合にはwarning
        if len(total_df) == 0:
            logger.warning(f"対象プロジェクトの労務管理情報・作業情報が0件のため、出力しません。")
            return
        total_df = refine_df(total_df, start_date, end_date, user_id_list)
        if len(total_df) == 0:
            logger.warning(f"対象期間の労務管理情報・作業情報が0件のため、出力しません。")
            return

        # 時間単位変換
        total_df = timeunit_conversion(df=total_df, time_unit=time_unit)

        # フォーマット別に出力dfを作成
        if format_target == FormatTarget.BY_NAME_TOTAL:
            df = print_byname_total_list(total_df)
        elif format_target == FormatTarget.TOTAL:
            df = print_total(total_df)
        elif format_target == FormatTarget.COLUMN_LIST_PER_PROJECT:
            df = create_column_list_per_project(total_df)
        elif format_target == FormatTarget.COLUMN_LIST:
            df = create_column_list(total_df)
        elif format_target == FormatTarget.DETAILS:
            df = print_time_list_from_work_time_list(total_df)
        else:
            raise RuntimeError(f"format_target='{format_target}'は対象外です。")
        # 出力先別に出力
        if args.output:
            out_format = args.output
        else:
            out_format = sys.stdout
        self._output(
            out_format,
            df,
            index=(format_target == FormatTarget.DETAILS),
            add_project_id=args.add_project_id,
            project_id_list=project_id_list,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListLaborWorktime(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    time_unit_choices = [e.value for e in TimeUnitTarget]
    format_choices = [e.value for e in FormatTarget]
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="集計対象のプロジェクトのproject_idを指定します。複数指定した場合は合計値を出力します。`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        default=None,
        help="集計対象のユーザのuser_idに部分一致するものを集計します。"
        "指定しない場合は、プロジェクトメンバが指定されます。`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument("--start_date", type=str, required=True, help="集計開始日(YYYY-mm-dd)")
    parser.add_argument("--end_date", type=str, required=True, help="集計終了日(YYYY-mm-dd)")

    parser.add_argument("--time_unit", type=str, default="h", choices=time_unit_choices, help="出力の時間単位(h/m/s)")
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=format_choices,
        default="details",
        help="出力する際のフォーマットです。デフォルトは'details'です。"
        "details:日毎・人毎の詳細な値を出力する, "
        "total:期間中の合計値だけを出力する, "
        "by_name_total:人毎の集計の合計値を出力する, "
        "column_list:列固定で詳細な値を出力する, "
        "column_list_per_project:列固定で詳細な値をプロジェクトごとに出力する, ",
    )
    parser.add_argument("--add_project_id", action="store_true", help="出力する際にprojectidを出力する")
    argument_parser.add_output(required=False)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_worktime"
    subcommand_help = "労務管理画面の作業時間を出力します。"
    description = "作業者ごとに、「作業者が入力した実績時間」と「AnnoFabが集計した作業時間」の差分を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
