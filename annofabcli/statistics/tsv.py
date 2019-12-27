import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd
from annofabapi.models import TaskPhase

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

    def _write_csv(self, filename: str, df):
        """
        カンマ区切りでBOM UTF-8で書きこむ(Excelで開けるようにするため）
        Args:
            filename: ファイル名
            df: DataFrame

        Returns:

        """
        output_path = Path(f"{self.outdir}/{filename}")
        output_path.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{str(output_path)} 書き込み")
        df.to_csv(str(output_path), sep=",", encoding="utf_8_sig", index=False)

    @staticmethod
    def _create_required_columns(df, prior_columns, dropped_columns):
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        if dropped_columns is not None:
            for key in dropped_columns:
                if key in all_columns:
                    all_columns.remove(key)
        return all_columns

    def __init__(self, outdir: str, project_id: str):
        self.outdir = outdir
        self.short_project_id = project_id[0:8]

    def write_inspection_list(
        self, df: pd.DataFrame, dropped_columns: Optional[List[str]] = None, only_error_corrected: bool = True,
    ):
        """
        検査コメント一覧をTSVで出力する
        Args:
            df
            dropped_columns:

        Returns:

        """
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

        if only_error_corrected:
            suffix = "返信を除く_修正不要を除く"
        else:
            suffix = "返信を除く_修正不要を含む"

        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.short_project_id}-検査コメントlist-{suffix}.csv", df[required_columns])

    def write_task_list(self, df: pd.DataFrame, dropped_columns: List[str] = None):
        """
        タスク一覧をTSVで出力する
        Args:
            arg_df:
            dropped_columns:

        Returns:

        """
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
            "sampling",
            # 1回目の教師付フェーズ
            "first_annotation_user_id",
            "first_annotation_worktime_hour",
            "first_annotation_started_datetime",
            # 1回目の検査フェーズ
            "first_inspection_user_id",
            "first_inspection_worktime_hour",
            "first_inspection_started_datetime",
            # 1回目の受入フェーズ
            "first_acceptance_user_id",
            "first_acceptance_worktime_hour",
            "first_acceptance_started_datetime",
            # 作業時間に関する内容
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "first_annotation_worktime_hour",
            "first_inspection_worktime_hour",
            "first_acceptance_worktime_hour",
            "first_annotator_worktime_hour",
            "first_inspector_worktime_hour",
            "first_acceptor_worktime_hour",
            # 個数
            "input_data_count",
            "annotation_count",
            "inspection_count",
            "input_data_count_of_inspection",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.short_project_id}-タスクlist.csv", df[required_columns])

    def write_task_history_list(self, df: pd.DataFrame, dropped_columns: List[str] = None) -> None:
        """
        タスク履歴一覧をCSVで出力する

        Args:
            arg_df:
            dropped_columns:

        Returns:

        """
        if len(df) == 0:
            logger.info("タスク履歴一覧が0件のため出力しない")
            return

        prior_columns = [
            "project_id",
            "task_id",
            "task_history_id",
            "phase",
            "phase_stage",
            "started_datetime",
            "ended_datetime",
            "user_id",
            "username",
            "worktime_hour",
        ]

        df = df.sort_values(["task_id", "started_datetime"])
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.short_project_id}-タスク履歴list.csv", df[required_columns])

    def write_member_list(self, df: pd.DataFrame, dropped_columns: List[str] = None):
        """
        プロジェクトメンバ一覧をTSVで出力する
        Args:
            arg_df:
            dropped_columns:

        Returns:

        """
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
        self._write_csv(f"{self.short_project_id}-メンバlist.csv", df[required_columns])

    def write_ラベルごとのアノテーション数(self, df: pd.DataFrame):
        """
        アノテーションラベルごとの個数を出力
        """
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
        self._write_csv(f"{self.short_project_id}-タスクlist-ラベルごとのアノテーション数.csv", df[required_columns])

    def write_教師付作業者別日毎の情報(self, df: pd.DataFrame):
        """
        ユーザごと、日毎の作業時間一覧をTSVで出力する. タスク一覧とは無関係。
        """
        if len(df) == 0:
            logger.info("データが0件のため、教師付作業者別日毎の情報は出力しない。")
            return

        prior_columns = [
            "first_annotation_started_date",
            "first_annotation_username",
            "first_annotation_user_id",
            "task_count",
            "input_data_count",
            "annotation_count",
            "first_annotation_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "inspection_count",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns=None)
        self._write_csv(f"{self.short_project_id}_教師付者_教師付開始日list.csv", df[required_columns])

    def write_ユーザ別日毎の作業時間(self, df: pd.DataFrame):
        """
        ユーザごと、日毎の作業時間一覧をTSVで出力する. タスク一覧とは無関係。
        """
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
        self._write_csv(f"{self.short_project_id}-ユーザ_日付list-作業時間.csv", df[required_columns])

    def write_メンバー別作業時間平均_画像1枚あたり(self, df: pd.DataFrame, phase: TaskPhase):
        if len(df) == 0:
            logger.info(f"メンバー別画像1枚当たりの作業時間平均-{phase.value} 一覧が0件のため、出力しない")
            return
        self._write_csv(f"画像1枚当たり作業時間/{self.short_project_id}_画像1枚当たり作業時間_{phase.value}.csv", df)

    def write_メンバー別作業時間平均_タスク1個あたり(self, df: pd.DataFrame, phase: TaskPhase):
        if len(df) == 0:
            logger.info(f"メンバ別タスク1個当たりの作業時間平均-{phase.value} 一覧が0件のため、出力しない")
            return
        self._write_csv(f"タスク1個当たり作業時間/{self.short_project_id}_タスク1個当たり作業時間_{phase.value}.csv", df)
