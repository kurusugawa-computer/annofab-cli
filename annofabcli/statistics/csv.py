import logging
from pathlib import Path
from typing import Any, List, Optional

import pandas
from annofabapi.models import TaskPhase

from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


class Csv:
    """
    CSVを出力するクラス
    """

    CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}

    def __init__(self, outdir: str, filename_prefix: Optional[str] = None):
        self.outdir = outdir
        self.filename_prefix = filename_prefix + "-" if filename_prefix is not None else ""

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
    def _create_required_columns(
        df: pandas.DataFrame, prior_columns: List[Any], dropped_columns: Optional[List[Any]] = None
    ) -> List[str]:
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        if dropped_columns is not None:
            for key in dropped_columns:
                if key in all_columns:
                    all_columns.remove(key)
        return all_columns

    def write_inspection_list(
        self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None, only_error_corrected: bool = True,
    ) -> None:
        """
        検査コメント一覧をTSVで出力する
        Args:
            df
            dropped_columns:
            only_error_corrected:

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
        self._write_csv(f"{self.filename_prefix}検査コメントlist-{suffix}.csv", df[required_columns])

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

        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.filename_prefix}タスクlist.csv", df[required_columns])

    def write_task_history_list(self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None) -> None:
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
        self._write_csv(f"{self.filename_prefix}タスク履歴list.csv", df[required_columns])

    def write_labor_list(self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None) -> None:
        """
        労務管理一覧をCSVで出力する

        Args:
            df:
            dropped_columns:

        Returns:

        """
        if len(df) == 0:
            logger.info("労務管理情報の一覧が0件のため出力しない")
            return

        prior_columns = [
            "date",
            "account_id",
            "user_id",
            "username",
            "biography",
            "worktime_plan_hour",
            "worktime_result_hour",
        ]

        df = df.sort_values(["date", "user_id"])
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.filename_prefix}労務管理list.csv", df[required_columns])

    def write_worktime_summary(self, df: pandas.DataFrame) -> None:
        """
        作業時間に関する集計結果をCSVで出力する。

        Args:
            df: タスクListのDataFrame

        """
        columns = [
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "first_annotator_worktime_hour",
            "first_inspector_worktime_hour",
            "first_acceptor_worktime_hour",
            "first_annotation_worktime_hour",
            "first_inspection_worktime_hour",
            "first_acceptance_worktime_hour",
        ]
        stat_df = df[columns].describe().T
        stat_df["sum"] = df[columns].sum().values
        stat_df["column"] = stat_df.index

        # 自動検査されたタスクを除外
        ignored_auto_inspection_df = df[~df["inspection_is_skipped"]]
        columns_inspection = [
            "inspection_worktime_hour",
            "first_inspector_worktime_hour",
            "first_inspection_worktime_hour",
        ]
        stat_inspection_df = ignored_auto_inspection_df[columns_inspection].describe().T
        stat_inspection_df["sum"] = df[columns_inspection].sum().values
        stat_inspection_df["column"] = stat_inspection_df.index + "_ignored_auto_inspection"

        # 自動受入されたタスクを除外
        ignore_auto_acceptance_df = df[~df["acceptance_is_skipped"]]
        columns_acceptance = [
            "acceptance_worktime_hour",
            "first_acceptor_worktime_hour",
            "first_acceptance_worktime_hour",
        ]
        stat_acceptance_df = ignore_auto_acceptance_df[columns_acceptance].describe().T
        stat_acceptance_df["sum"] = df[columns_acceptance].sum().values
        stat_acceptance_df["column"] = stat_acceptance_df.index + "_ignored_auto_acceptance"

        target_df = pandas.concat([stat_df, stat_inspection_df, stat_acceptance_df])
        target_df = target_df[["column", "mean", "std", "min", "25%", "50%", "75%", "max", "count", "sum"]]

        self._write_csv(f"集計結果csv/{self.filename_prefix}集計-作業時間.csv", target_df)

    def write_count_summary(self, df: pandas.DataFrame) -> None:
        """
        個数に関する集計結果をCSVで出力する。

        Args:
            df: タスクListのDataFrame

        """
        columns = [
            "input_data_count",
            "annotation_count",
            "inspection_count",
        ]
        stat_df = df[columns].describe().T
        stat_df["sum"] = df[columns].sum().values
        stat_df["column"] = stat_df.index

        target_df = stat_df[["column", "mean", "std", "min", "25%", "50%", "75%", "max", "count", "sum"]]

        self._write_csv(f"集計結果csv/{self.filename_prefix}集計-個数.csv", target_df)

    def write_task_count_summary(self, df: pandas.DataFrame) -> None:
        """
        タスク数の集計結果をCSVで出力する。

        Args:
            df: タスクListのDataFrame

        """
        columns = [
            "annotator_is_changed",
            "inspector_is_changed",
            "acceptor_is_changed",
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

        sum_series = df[columns].sum()
        sum_df = pandas.DataFrame()
        sum_df["column"] = sum_series.index
        sum_df["count_if_true"] = sum_series.values
        sum_df = sum_df.append({"column": "task_count", "count_if_true": len(df)}, ignore_index=True)
        self._write_csv(f"集計結果csv/{self.filename_prefix}集計-タスク数.csv", sum_df)

    def write_member_list(self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None):
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
            "biography",
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
        self._write_csv(f"{self.filename_prefix}メンバlist.csv", df[required_columns])

    def write_ラベルごとのアノテーション数(self, df: pandas.DataFrame):
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
        self._write_csv(f"{self.filename_prefix}タスクlist-ラベルごとのアノテーション数.csv", df[required_columns])

    def write_教師付作業者別日毎の情報(self, df: pandas.DataFrame):
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
        self._write_csv(f"{self.filename_prefix}_教師付者_教師付開始日list.csv", df[required_columns])

    def write_ユーザ別日毎の作業時間(self, df: pandas.DataFrame):
        """
        ユーザごと、日毎の作業時間一覧をTSVで出力する. タスク一覧とは無関係。
        """
        if len(df) == 0:
            logger.info("ユーザ別日毎の作業時間一覧が0件のため出力しない")
            return

        prior_columns = [
            "user_id",
            "username",
            "biography",
            "date",
            "tasks_completed",
            "tasks_rejected",
            "worktime_hour",
        ]
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns=None)
        self._write_csv(f"{self.filename_prefix}ユーザ_日付list-作業時間.csv", df[required_columns])

    def write_メンバー別作業時間平均_画像1枚あたり(self, df: pandas.DataFrame, phase: TaskPhase):
        if len(df) == 0:
            logger.info(f"メンバー別画像1枚当たりの作業時間平均-{phase.value} 一覧が0件のため、出力しない")
            return
        self._write_csv(f"画像1枚当たり作業時間/{self.filename_prefix}_画像1枚当たり作業時間_{phase.value}.csv", df)

    def write_メンバー別作業時間平均_タスク1個あたり(self, df: pandas.DataFrame, phase: TaskPhase):
        if len(df) == 0:
            logger.info(f"メンバ別タスク1個当たりの作業時間平均-{phase.value} 一覧が0件のため、出力しない")
            return
        self._write_csv(f"タスク1個当たり作業時間/{self.filename_prefix}_タスク1個当たり作業時間_{phase.value}.csv", df)

    def write_productivity_from_aw_time(
        self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None, output_path: Optional[Path] = None
    ):
        """
        メンバごとの生産性を出力する。

        Args:
            df:
            dropped_columns:

        Returns:

        """

        def get_phase_list() -> List[str]:
            columns = list(df.columns)
            phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
            if ("monitored_worktime_hour", TaskPhase.INSPECTION.value) not in columns:
                phase_list.remove(TaskPhase.INSPECTION.value)
            if ("monitored_worktime_hour", TaskPhase.ACCEPTANCE.value) not in columns:
                phase_list.remove(TaskPhase.ACCEPTANCE.value)
            return phase_list

        if len(df) == 0:
            logger.info("プロジェクトメンバ一覧が0件のため出力しない")
            return

        phase_list = get_phase_list()

        user_columns = [("user_id", ""), ("username", ""), ("biography", ""), ("last_working_date", "")]

        monitored_worktime_columns = (
            [("monitored_worktime_hour", phase) for phase in phase_list]
            + [("monitored_worktime_hour", "sum")]
            + [("monitored_worktime_ratio", phase) for phase in phase_list]
        )
        production_columns = (
            [("task_count", phase) for phase in phase_list]
            + [("input_data_count", phase) for phase in phase_list]
            + [("annotation_count", phase) for phase in phase_list]
        )

        actual_worktime_columns = [("actual_worktime_hour", "sum")] + [
            ("prediction_actual_worktime_hour", phase) for phase in phase_list
        ]

        productivity_columns = (
            [("monitored_worktime/input_data_count", phase) for phase in phase_list]
            + [("actual_worktime/input_data_count", phase) for phase in phase_list]
            + [("monitored_worktime/annotation_count", phase) for phase in phase_list]
            + [("actual_worktime/annotation_count", phase) for phase in phase_list]
        )

        inspection_comment_columns = [
            ("pointed_out_inspection_comment_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/input_data_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/annotation_count", TaskPhase.ANNOTATION.value),
        ]

        prior_columns = (
            user_columns
            + monitored_worktime_columns
            + production_columns
            + actual_worktime_columns
            + productivity_columns
            + inspection_comment_columns
        )
        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        target_df = df[required_columns]
        if output_path is None:
            self._write_csv(f"{self.filename_prefix}メンバごとの生産性と品質.csv", target_df)
        else:
            print_csv(df, output=str(output_path), to_csv_kwargs=self.CSV_FORMAT)

    def write_whole_productivity_per_date(
        self, df: pandas.DataFrame, dropped_columns: Optional[List[str]] = None
    ) -> None:
        """
        日毎の全体の生産量、生産性を出力する。

        Args:
            df:
            dropped_columns:


        """
        production_columns = [
            "task_count",
            "input_data_count",
            "annotation_count",
        ]
        worktime_columns = [
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "monitored_annotation_worktime_hour",
            "monitored_inspection_worktime_hour",
            "monitored_acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for numerator in ["actual_worktime_hour", "monitored_worktime_hour"]
            for denominator in ["task_count", "input_data_count", "annotation_count"]
            for suffix in ["", "__lastweek"]
        ]

        prior_columns = (
            ["date", "cumsum_task_count", "cumsum_input_data_count", "cumsum_actual_worktime_hour"]
            + production_columns
            + worktime_columns
            + velocity_columns
            + ["working_user_count"]
        )

        required_columns = self._create_required_columns(df, prior_columns, dropped_columns)
        self._write_csv(f"{self.filename_prefix}日毎の生産量と生産性.csv", df[required_columns])
