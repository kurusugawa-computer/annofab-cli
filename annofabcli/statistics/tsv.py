import logging
from typing import List

import pandas as pd

from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


class Tsv:
    """
    TSVを出力するクラス
    """

    #############################################
    # Field
    #############################################

    #############################################
    # Private
    #############################################

    def _write_tsv(self, filename: str, df):
        """
        TSVでBOM UTF-8で書きこむ(Excelで開けるようにするため）
        Args:
            filename: ファイル名
            df: DataFrame

        Returns:

        """
        filepath = f"{self.outdir}/{filename}"
        logger.debug(f"{filepath} 書き込み")
        df.to_csv(filepath, sep=",", encoding="utf_8_sig")

    @staticmethod
    def _create_required_columns(df, prior_columns, dropped_columns):
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        if dropped_columns is not None:
            for key in dropped_columns:
                if key in all_columns:
                    all_columns.remove(key)
        return all_columns

    def __init__(self, table: Table, outdir: str):
        self.table = table
        self.outdir = outdir
        self.short_project_id = table.project_id[0:8]

    def write_inspection_list(self, arg_df: pd.DataFrame = None, dropped_columns: List[str] = None):
        """
        検査コメント一覧をTSVで出力する
        Args:
            arg_df
            dropped_columns:

        Returns:

        """
        df = self.table.create_inspection_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("検査コメント一覧が0件のため出力しない")
            return

        prior_columns = [
            "inspection_id",
            "task_id",
            "input_data_id",
            "phase",
            "status",
            "commenter_user_id",
            "label_name",
            "comment",
            "phrases",
            "phrases_name",
            "created_datetime",
            "updated_datetime",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_tsv(f"{self.short_project_id}_検査コメント一覧_返信_修正不要を除く.csv", df[required_columns])

        df_all = self.table.create_inspection_df(only_error_corrected=False)
        self._write_tsv(f"{self.short_project_id}_検査コメント一覧_返信を除く_修正不要を含む.csv", df_all[required_columns])

    def write_task_list(self, arg_df: pd.DataFrame = None, dropped_columns: List[str] = None):
        """
        タスク一覧をTSVで出力する
        Args:
            arg_df:
            dropped_columns:

        Returns:

        """
        df = self.table.create_task_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        prior_columns = [
            "project_id",
            "task_id",
            "phase",
            "status",
            "user_id",
            "number_of_rejections",
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            "started_datetime",
            "updated_datetime",
            "started_date",
            "updated_date",
            "sampling",

            # 最初のアノテーション作業に関すること
            "first_annotation_user_id",
            "first_annotation_worktime_hour",
            "first_annotation_started_datetime",
            # 作業時間に関する内容
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 個数
            "input_data_count",
            "annotation_count",
            "inspection_count",
            "input_data_count_of_inspection",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_tsv(f"{self.short_project_id}_タスク一覧.csv", df[required_columns])

    def write_member_list(self, arg_df: pd.DataFrame = None, dropped_columns: List[str] = None):
        """
        プロジェクトメンバ一覧をTSVで出力する
        Args:
            arg_df:
            dropped_columns:

        Returns:

        """
        df = self.table.create_member_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("プロジェクトメンバ一覧が0件のため出力しない")
            return

        prior_columns = [
            "user_id",
            "username",
            "member_role",
            "member_status",

            # 関わった作業時間
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",

            # 初回のアノテーションに関わった個数（タスクの教師付担当者は変更されない前提）
            "task_count_of_first_annotation",
            "input_data_count_of_first_annotation",
            "annotation_count_of_first_annotation",
            "inspection_count_of_first_annotation",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_tsv(f"{self.short_project_id}_メンバ一覧.csv", df[required_columns])

    def write_ラベルごとのアノテーション数(self, arg_df: pd.DataFrame = None):
        """
        アノテーションラベルごとの個数を出力
        """
        df = self.table.create_task_for_annotation_df() if arg_df is None else arg_df
        if len(df) == 0:
            logger.info("アノテーションラベルごとの一覧が0件のため出力しない")
            return

        prior_columns = [
            "task_id",
            "input_data_count",
            "status",
            "phase",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns=None)
        self._write_tsv(f"{self.short_project_id}_ラベルごとのアノテーション数.csv", df[required_columns])

    def write_ユーザ別日毎の作業時間(self):
        """
        ユーザごと、日毎の作業時間一覧をTSVで出力する. タスク一覧とは無関係。
        """
        df = self.table.create_account_statistics_df()
        if len(df) == 0:
            logger.info("ユーザ別日毎の作業時間一覧が0件のため出力しない")
            return

        prior_columns = [
            "user_id",
            "username",
            "date",
            "tasks_completed",
            "tasks_rejected",
            "worktime_hour",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns=None)
        self._write_tsv(f"{self.short_project_id}_ユーザ別日毎の作業時間.csv", df[required_columns])
