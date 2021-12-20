import logging
from pathlib import Path
from typing import Any, List, Optional

import pandas

logger = logging.getLogger(__name__)

FILENAME_WHOLE_PERFORMANCE = "全体の生産性と品質.csv"
FILENAME_PERFORMANCE_PER_USER = "メンバごとの生産性と品質.csv"

FILENAME_PERFORMANCE_PER_DATE = "日毎の生産量と生産性.csv"
FILENAME_PERFORMANCE_PER_FIRST_ANNOTATION_STARTED_DATE = "教師付開始日毎の生産量と生産性.csv"
FILENAME_TASK_LIST = "タスクlist.csv"


class Csv:
    """
    CSVを出力するクラス
    """

    CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}

    def __init__(self, outdir: str):
        self.outdir = outdir

    #############################################
    # Field
    #############################################

    #############################################
    # Private
    #############################################

    def _write_csv(self, filename: str, df: pandas.DataFrame) -> None:
        """
        カンマ区切りでBOM UTF-8で書きこむ(Excelで開けるようにするため）
        Args:
            filename: ファイル名
            df: DataFrame

        Returns:

        """
        output_path = Path(f"{self.outdir}/{filename}")
        output_path.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{str(output_path)} を出力します。")
        df.to_csv(str(output_path), sep=",", encoding="utf_8_sig", index=False)

    @staticmethod
    def create_required_columns(
        df: pandas.DataFrame, prior_columns: List[Any], dropped_columns: Optional[List[Any]] = None
    ) -> List[str]:
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        if dropped_columns is not None:
            for key in dropped_columns:
                if key in all_columns:
                    all_columns.remove(key)
        return all_columns

    def write_task_list(self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None) -> None:
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
            "phase_stage",
            "status",
            "user_id",
            "username",
            "number_of_rejections",
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            "started_datetime",
            "updated_datetime",
            "task_completed_datetime",
            "sampling",
            # 1回目の教師付フェーズ
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_worktime_hour",
            "first_annotation_started_datetime",
            # 1回目の検査フェーズ
            "first_inspection_user_id",
            "first_inspection_username",
            "first_inspection_worktime_hour",
            "first_inspection_started_datetime",
            # 1回目の受入フェーズ
            "first_acceptance_user_id",
            "first_acceptance_username",
            "first_acceptance_worktime_hour",
            "first_acceptance_started_datetime",
            # 作業時間に関する内容
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "first_annotator_worktime_hour",
            "first_inspector_worktime_hour",
            "first_acceptor_worktime_hour",
            # 個数
            "input_data_count",
            "input_duration_seconds",
            "annotation_count",
            "inspection_count",
            "input_data_count_of_inspection",
            # タスクの状態
            "annotator_is_changed",
            "inspector_is_changed",
            "acceptor_is_changed",
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

        if dropped_columns is None:
            dropped_columns = []
        dropped_columns.extend(
            [
                "first_acceptance_account_id",
                "first_annotation_account_id",
                "first_annotation_started_date",
                "first_inspection_account_id",
                "task_count",
                "account_id",
                "work_time_span",
            ]
        )

        required_columns = self.create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(FILENAME_TASK_LIST, df[required_columns])
