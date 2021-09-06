import argparse
import datetime
import logging
import multiprocessing
import sys
from dataclasses import dataclass
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
import numpy
import numpy as np
import pandas
import pandas as pd
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.utils import isoduration_to_hour, print_csv

logger = logging.getLogger(__name__)


@dataclass
class DailyTimesPerProject(DataClassJsonMixin):
    """日ごと、メンバごと、プロジェクトごとの作業時間"""

    project_id: str
    project_name: str
    project_group: str
    date: str

    account_id: str
    user_id: str
    user_name: str
    user_biography: str
    worktime_actual: float
    """実績作業時間[hour]"""
    worktime_planned: float
    """予定作業時間[hour]"""
    worktime_monitored: float
    """Annofabの計測作業時間[hour]"""


@dataclass
class DailyMonitoredWorktime(DataClassJsonMixin):
    """日ごとの計測作業時間情報"""

    project_id: str
    account_id: str
    date: str
    worktime_monitored: float
    """Annofabの計測作業時間[hour]"""


@dataclass
class DailyLaborWorktime(DataClassJsonMixin):
    """日ごとの実績作業時間と予定作業時間の情報"""

    project_id: str
    account_id: str
    date: str
    worktime_actual: float
    """実績作業時間[hour]"""
    worktime_planned: float
    """予定作業時間[hour]"""
    working_description: Optional[str]


class FormatTarget(Enum):
    DETAILS = "details"
    """日毎・人毎の詳細な値を出力する"""
    TOTAL = "total"
    """期間中の合計値だけを出力する"""
    BY_NAME_TOTAL = "by_name_total"
    """人毎の集計の合計値を出力する"""
    COLUMN_LIST = "column_list"
    """列固定で詳細な値を出力する"""
    COLUMN_LIST_PER_PROJECT = "column_list_per_project"
    """列固定で、日、メンバ、AnnoFabプロジェクトごとの作業時間を出力する"""
    INTERMEDIATE = "intermediate"
    """中間ファイル。このファイルからいろんな形式に変換できる。"""


DEFAULT_TO_REPLACE_FOR_VALUE = {numpy.inf: "--", numpy.nan: "--"}


def create_df_with_format_column_list_per_project(df_actual_times: pandas.DataFrame) -> pandas.DataFrame:
    """`--format column_list_per_project`に対応するDataFrameを生成する。

    Args:
        df (pd.DataFrame): [description]

    Returns:
        pd.DataFrame: [description]
    """
    df = df_actual_times.copy()

    # 元のコマンドの出力結果にできるだけ近づける

    df["activity_rate"] = df["worktime_actual"] / df["worktime_planned"]
    df["monitor_rate"] = df["worktime_monitored"] / df["worktime_actual"]

    return (
        df[
            [
                "date",
                "project_id",
                "project_title",
                "user_id",
                "user_name",
                "user_biography",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
                "working_description",
            ]
        ]
        .round(2)
        .replace(DEFAULT_TO_REPLACE_FOR_VALUE)
    )


def create_df_with_format_by_name_total(df_intermediate: pandas.DataFrame) -> pandas.DataFrame:
    """`--format by_name_total`に対応するDataFrameを生成する。

    Args:
        df (pd.DataFrame): [description]

    Returns:
        pd.DataFrame: [description]
    """
    df = df_intermediate.groupby("member_id")[
        ["actual_worktime_hour", "af_monitored_worktime_hour", "assigned_worktime_hour"]
    ].sum()
    df_user = df_intermediate.groupby("member_id").first()[["user_account", "company", "member_name"]]
    df = df.join(df_user)

    df.rename(
        columns={
            "user_account": "user_id",
            "company": "user_biography",
            "member_name": "user_name",
            "actual_worktime_hour": "worktime_actual",
            "af_monitored_worktime_hour": "worktime_monitored",
            "assigned_worktime_hour": "worktime_planned",
        },
        inplace=True,
    )

    df["activity_rate"] = df["worktime_actual"] / df["worktime_planned"]
    df["monitor_rate"] = df["worktime_monitored"] / df["worktime_actual"]

    return (
        df[
            [
                "user_id",
                "user_name",
                "user_biography",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
            ]
        ]
        .round(2)
        .replace(DEFAULT_TO_REPLACE_FOR_VALUE)
    )


def create_df_with_format_column_list(df_intermediate: pandas.DataFrame) -> pandas.DataFrame:
    """`--format column_list`に対応するDataFrameを生成する。
    日ごと、ユーザごとに、作業時間を出力する。

    Args:
        df (pd.DataFrame): [description]

    Returns:
        pd.DataFrame: `--format column_list`に対応するDataFrame
    """
    df = df_intermediate.groupby(["date", "member_id"])[
        ["actual_worktime_hour", "af_monitored_worktime_hour", "assigned_worktime_hour"]
    ].sum()
    df_user = df_intermediate.groupby("member_id").first()[["user_account", "company", "member_name"]]
    df = df.join(df_user)

    df.rename(
        columns={
            "user_account": "user_id",
            "company": "user_biography",
            "member_name": "user_name",
            "actual_worktime_hour": "worktime_actual",
            "af_monitored_worktime_hour": "worktime_monitored",
            "assigned_worktime_hour": "worktime_planned",
        },
        inplace=True,
    )

    df["activity_rate"] = df["worktime_actual"] / df["worktime_planned"]
    df["monitor_rate"] = df["worktime_monitored"] / df["worktime_actual"]

    # indexのdateを列名にする
    print(f"{df.index}")
    df.reset_index(level="date", inplace=True)
    return (
        df[
            [
                "date",
                "user_id",
                "user_name",
                "user_biography",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
            ]
        ]
        .round(2)
        .replace(DEFAULT_TO_REPLACE_FOR_VALUE)
    )


def create_df_with_format_details(
    df_intermediate: pandas.DataFrame, insert_sum_row: bool = True, insert_sum_column: bool = True
) -> pandas.DataFrame:
    """`--format details`に対応するDataFrameを生成する。

    Args:
        df (pd.DataFrame): 中間出力用のDataFrame
        insert_sum_row: 合計行を追加する
        insert_sum_column: 合計列を追加する

    Returns:
        pd.DataFrame: `--format details`に対応するDataFrame

    Notes:
        fork元のannofabcliには、AnnoFabプロジェクトのproject_idの一覧も記載されていたが、なくても問題ないため省く。
    """
    SUM_COLUMN_NAME = "総合計"
    SUM_ROW_NAME = "合計"

    # TODO 同姓同名だった場合、正しく集計されない
    df = df_intermediate.groupby(["date", "username"])[
        ["worktime_actual", "worktime_monitored", "worktime_planned"]
    ].sum()

    if insert_sum_column:
        df_sum_by_date = df_intermediate.groupby(["date"])[
            ["worktime_actual", "worktime_monitored", "worktime_planned"]
        ].sum()
        # 列名が"総合計"になるように、indexを変更する
        df_sum_by_date.index = [(date, SUM_COLUMN_NAME) for date in df_sum_by_date.index]

        df = df.append(df_sum_by_date)

    # ヘッダが [member_id, value] になるように設定する
    df2 = df.stack().unstack([1, 2])

    # 日付が連続になるようにする
    not_exists_date_set = {str(e.date()) for e in pandas.date_range(start=min(df2.index), end=max(df2.index))} - set(
        df2.index
    )
    df2 = df2.append([pandas.Series(name=date, dtype="float64") for date in not_exists_date_set], sort=True)

    # 作業時間がNaNの場合は0に置換する
    df2.replace(
        {
            col: {numpy.nan: 0}
            for col in df2.columns
            if col[1] in ["worktime_actual", "worktime_monitored", "worktime_planned"]
        },
        inplace=True,
    )

    username_list = list(df_intermediate["username"].unique())
    if insert_sum_column:
        username_list = [SUM_COLUMN_NAME] + username_list

    if insert_sum_row:
        # 先頭行に合計を追加する
        tmp_sum_row = df2.sum()
        tmp_sum_row.name = SUM_ROW_NAME
        df2 = pandas.concat([pandas.DataFrame([tmp_sum_row]), df2])

    for username in username_list:
        df2[(username, "activity_rate")] = df2[(username, "worktime_actual")] / df2[(username, "worktime_planned")]
        df2[(username, "monitor_rate")] = df2[(username, "worktime_monitored")] / df2[(username, "worktime_actual")]

    # 比率がNaNの場合は"--"に置換する
    df2.replace(
        {col: DEFAULT_TO_REPLACE_FOR_VALUE for col in df2.columns if col[1] in ["activity_rate", "monitor_rate"]},
        inplace=True,
    )

    # 列の順番を整える
    df2 = df2[
        [
            (m, v)
            for m in username_list
            for v in ["worktime_planned", "worktime_actual", "worktime_monitored", "activity_rate", "monitor_rate"]
        ]
    ]
    # date列を作る
    df2.reset_index(inplace=True)
    return df2.round(2)


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


class ListLaborWorktimeMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def _get_monitored_worktime(self, project_id: str, start_date: str, end_date: str) -> List[DailyMonitoredWorktime]:
        """計測作業時間の情報を取得

        Args:
            project_id: Annofab プロジェクトのproject_id
            start_date (str): [description]
            end_date (str): [description]
        """
        account_statistics = self.service.wrapper.get_account_statistics(project_id)

        result = []
        for account_info in account_statistics:
            account_id = account_info["account_id"]
            histories = account_info["histories"]
            for history in histories:
                worktime_hour = isoduration_to_hour(history["worktime"])
                if start_date <= history["date"] <= end_date and worktime_hour > 0:
                    result.append(
                        DailyMonitoredWorktime(
                            project_id=project_id,
                            account_id=account_id,
                            date=history["date"],
                            worktime_monitored=worktime_hour,
                        )
                    )

        return result

    def _get_labor_worktime(self, project_id: str, start_date: str, end_date: str) -> List[DailyLaborWorktime]:

        labor_list = self.service.wrapper.get_labor_control_worktime(
            project_id=project_id, from_date=start_date, to_date=end_date
        )

        new_labor_list: List[DailyLaborWorktime] = []
        for labor in labor_list:
            new_labor = DailyLaborWorktime(
                project_id=labor["project_id"],
                account_id=labor["account_id"],
                date=labor["date"],
                worktime_actual=labor["actual_worktime"] if labor["actual_worktime"] is not None else 0,
                worktime_planned=labor["plan_worktime"] if labor["plan_worktime"] is not None else 0,
                working_description=labor["working_description"],
            )

            if new_labor.worktime_actual > 0 or new_labor.worktime_planned > 0:
                new_labor_list.append(new_labor)
        return new_labor_list

    def create_intermediate_df_for_one_project(
        self, project_id: str, *, start_date: str, end_date: str, project_index: Optional[int] = None
    ) -> pandas.DataFrame:

        OUTPUT_COLUMNS = [
            "date",
            "project_id",
            "project_title",
            "account_id",
            "user_id",
            "user_name",
            "user_biography",
            "worktime_planned",
            "worktime_actual",
            "worktime_monitored",
            "working_description",
        ]

        project, _ = self.service.api.get_project(project_id)

        logging_prefix = f"{project_index+1} 件目" if project_index is not None else ""
        logger.debug(f"{logging_prefix}: project_id='{project_id}', project_title='{project['title']}'の作業時間情報を取得します。")
        labor_worktime = self._get_labor_worktime(project_id=project_id, start_date=start_date, end_date=end_date)
        monitored_worktime = self._get_monitored_worktime(project_id, start_date=start_date, end_date=end_date)
        project_member_list = self.service.wrapper.get_all_project_members(
            project_id, query_params={"include_inactive_member": ""}
        )

        df_labor_worktime = pandas.DataFrame(
            labor_worktime,
            columns=["project_id", "date", "account_id", "worktime_actual", "worktime_planned", "working_description"],
        )
        df_monitored_worktime = pandas.DataFrame(
            monitored_worktime, columns=["project_id", "date", "account_id", "worktime_monitored"]
        )
        df_project_member = pandas.DataFrame(
            project_member_list, columns=["account_id", "user_id", "username", "biography"]
        )
        df_project_member.rename(columns={"username":"user_name","biography":"user_biography"}, inplace=True)
        df_merged = pandas.merge(
            df_labor_worktime, df_monitored_worktime, how="outer", on=["date", "project_id", "account_id"]
        )
        df_merged.fillna({"worktime_actual": 0, "worktime_planned": 0, "worktime_monitored": 0}, inplace=True)

        df_merged["project_title"] = project["title"]
        df = pandas.merge(
            df_merged,
            df_project_member,
            how="left",
            on=["account_id"],
        )
        return df[OUTPUT_COLUMNS]

    def _create_intermediate_df_for_one_project_wrapper(
        self,
        tpl: Tuple[int, str],
        *,
        start_date: str,
        end_date: str,
    ):
        project_index, project_id = tpl
        return self.create_intermediate_df_for_one_project(
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
            project_index=project_index,
        )

    def create_intermediate_df(
        self, project_id_list: List[str], *, start_date: str, end_date: str, parallelism: Optional[int] = None
    ) -> pandas.DataFrame:
        """中間ファイルの元になるDataFrameを出力する。"""
        df_list = []
        logger.info(f"{len(project_id_list)} 件のプロジェクトの作業時間情報を取得します。")

        # 集計値を出力するので、1つでも作業時間情報の取得に失敗したら終了するようにする。

        if parallelism is not None:
            partial_func = partial(
                self._create_intermediate_df_for_one_project_wrapper,
                start_date=start_date,
                end_date=end_date,
            )
            with multiprocessing.Pool(parallelism) as pool:
                df_list = pool.map(partial_func, enumerate(project_id_list))

        else:
            # 逐次処理
            for project_index, project_id in enumerate(project_id_list):
                tmp_df = self.create_intermediate_df_for_one_project(
                    project_id, start_date=start_date, end_date=end_date, project_index=project_index
                )
                df_list.append(tmp_df)

        df = pandas.concat(df_list)
        return df

    def main(
        self,
        project_id_list: List[str],
        start_date: str,
        end_date: str,
        format_target: FormatTarget,
        output: Optional[Path] = None,
        parallelism: Optional[int] = None,
    ):

        df_intermediate = self.create_intermediate_df(
            project_id_list, start_date=start_date, end_date=end_date, parallelism=parallelism
        )
        if format_target == FormatTarget.COLUMN_LIST_PER_PROJECT:
            df_output = create_df_with_format_column_list_per_project(df_actual_times)

        elif format_target == FormatTarget.COLUMN_LIST:
            df_output = create_df_with_format_column_list(df_intermediate)

        elif format_target == FormatTarget.BY_NAME_TOTAL:
            df_output = create_df_with_format_by_name_total(df_intermediate)

        elif format_target == FormatTarget.DETAILS:
            df_output = create_df_with_format_details(df_intermediate)

        elif format_target == FormatTarget.INTERMEDIATE:
            df_output = df_intermediate

        else:
            raise RuntimeError(f"format_target={format_target} が不正です。")

        print_csv(df_output, str(output) if output is not None else None)


class ListLaborWorktime(AbstractCommandLineInterface):
    """
    労務管理画面の作業時間を出力する
    """

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

        project_id_list = get_list_from_args(args.project_id)

        main_obj = ListLaborWorktimeMain(self.service)
        main_obj.main(
            project_id_list,
            start_date=args.start_date,
            end_date=args.end_date,
            format_target=format_target,
            output=args.output,
            parallelism=args.parallelism,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
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
        help="集計対象のプロジェクトのproject_idを指定します。複数指定した場合は合計値を出力します。`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument("--start_date", type=str, required=True, help="集計開始日(YYYY-mm-dd)")
    parser.add_argument("--end_date", type=str, required=True, help="集計終了日(YYYY-mm-dd)")

    format_choices = [e.value for e in FormatTarget]
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=format_choices,
        default="intermediate",
        help="出力する際のフォーマットを指定してください。\n"
        "・details: 日毎/人毎の詳細な値を出力します。\n"
        "・total: 期間中の合計値だけを出力します。\n"
        "・by_name_total:人毎の集計の合計値を出力します。\n"
        "・column_list:列固定で詳細な値を出力します。\n"
        "・column_list_per_project: 列固定で、日、メンバ、AnnoFabプロジェクトごとの作業時間を出力します。\n"
        "・intermediate: `annofabcli experimental list_labor_worktime_from_csv`コマンドに渡せる中間ファイルを出力します。\n",
    )

    argument_parser.add_output(required=False)

    parser.add_argument("--parallelism", type=int, required=False, help="並列度。指定しない場合は、逐次的に処理します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_worktime"
    subcommand_help = "労務管理画面の作業時間を出力します。"
    description = "作業者ごとに、「作業者が入力した実績時間」と「AnnoFabが集計した作業時間」の差分を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
