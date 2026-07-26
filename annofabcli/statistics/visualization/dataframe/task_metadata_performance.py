from __future__ import annotations

import logging
from pathlib import Path

import numpy
import pandas
from annofabapi.models import TaskPhase

from annofabcli.common.utils import print_csv
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

logger = logging.getLogger(__name__)

EMPTY_METADATA_VALUE = ""
"""メタデータのキーが存在しない、または値がnullのタスクに設定する値。"""

METADATA_VALUE_COLUMN = "__task_metadata_value"
"""メタデータの値を一時的に格納する列名。"""


class TaskMetadataPerformance:
    """タスクのメタデータ値ごとの生産性と品質を表すDataFrameをラップするクラス。"""

    def __init__(
        self,
        df: pandas.DataFrame,
        metadata_key: str,
        *,
        custom_production_volume_list: list[ProductionVolumeColumn] | None = None,
    ) -> None:
        self.df = df
        self.metadata_key = metadata_key
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

    @property
    def production_volume_columns(self) -> list[str]:
        """生産量を表す列名。ただし`task_count`は除く。"""
        return ["input_data_count", "annotation_count", *[e.value for e in self.custom_production_volume_list]]

    @property
    def columns(self) -> list[tuple[str, str]]:
        """出力する列。"""
        phase_list = self._get_phase_list(self.df)
        production_volume_columns_with_task_count = ["task_count", *self.production_volume_columns]

        worktime_columns = [
            ("monitored_worktime_hour", "sum"),
            *[("monitored_worktime_hour", phase) for phase in phase_list],
            ("actual_worktime_hour", "sum"),
            *[("actual_worktime_hour", phase) for phase in phase_list],
        ]
        production_volume_columns = [(column, phase) for column in production_volume_columns_with_task_count for phase in phase_list]
        productivity_columns = [
            (f"{worktime_type}_worktime_hour/{column}", phase) for column in production_volume_columns_with_task_count for worktime_type in ["monitored", "actual"] for phase in phase_list
        ]
        quality_columns = [
            ("pointed_out_inspection_comment_count", TaskPhase.ANNOTATION.value),
            *[(f"pointed_out_inspection_comment_count/{column}", TaskPhase.ANNOTATION.value) for column in self.production_volume_columns],
            ("rejected_count", TaskPhase.ANNOTATION.value),
            ("rejected_count/task_count", TaskPhase.ANNOTATION.value),
        ]
        return [(self.metadata_key, ""), *worktime_columns, *production_volume_columns, *productivity_columns, *quality_columns]

    @staticmethod
    def _get_phase_list(df: pandas.DataFrame) -> list[str]:
        """DataFrameの列からフェーズ一覧を取得する。"""
        phases = [phase.value for phase in TaskPhase]
        return [phase for phase in phases if ("monitored_worktime_hour", phase) in df.columns]

    @staticmethod
    def _get_metadata_value_by_task_id(task: Task, metadata_key: str) -> pandas.DataFrame:
        """task_idごとのメタデータ値を取得する。"""
        df_task = task.df[["project_id", "task_id"]].copy()
        if "metadata" in task.df.columns:
            df_task[METADATA_VALUE_COLUMN] = task.df["metadata"].map(lambda metadata: metadata.get(metadata_key) if isinstance(metadata, dict) else None)
        else:
            df_task[METADATA_VALUE_COLUMN] = EMPTY_METADATA_VALUE
        return df_task[["project_id", "task_id", METADATA_VALUE_COLUMN]]

    @classmethod
    def from_df_wrapper(
        cls,
        task: Task,
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
        metadata_key: str,
        real_monitored_worktime_hour_per_real_actual_worktime_hour: float,
    ) -> TaskMetadataPerformance:
        """DataFrameのラッパーからインスタンスを生成する。"""
        metadata_value_by_task_id = cls._get_metadata_value_by_task_id(task, metadata_key)
        df = task_worktime_by_phase_user.df.merge(metadata_value_by_task_id, on=["project_id", "task_id"], how="left")
        df[METADATA_VALUE_COLUMN] = df[METADATA_VALUE_COLUMN].fillna(EMPTY_METADATA_VALUE)

        production_volume_columns = task_worktime_by_phase_user.production_volume_columns
        production_volume_columns_with_task_count = ["task_count", *production_volume_columns]
        value_columns = ["worktime_hour", *production_volume_columns_with_task_count, "pointed_out_inspection_comment_count", "rejected_count"]

        if len(df) == 0:
            return cls.empty(metadata_key, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

        df_result = df.pivot_table(index=METADATA_VALUE_COLUMN, columns="phase", values=value_columns, aggfunc="sum", fill_value=0)
        df_result = df_result.rename(columns={"worktime_hour": "monitored_worktime_hour"})

        with numpy.errstate(divide="ignore", invalid="ignore"):
            df_result[("monitored_worktime_hour", "sum")] = df_result["monitored_worktime_hour"].sum(axis=1)
            df_result[("actual_worktime_hour", "sum")] = df_result[("monitored_worktime_hour", "sum")] / real_monitored_worktime_hour_per_real_actual_worktime_hour

            phase_list = cls._get_phase_list(df_result)
            for phase in phase_list:
                df_result[("actual_worktime_hour", phase)] = df_result[("monitored_worktime_hour", phase)] / real_monitored_worktime_hour_per_real_actual_worktime_hour
                for column in production_volume_columns_with_task_count:
                    df_result[(f"monitored_worktime_hour/{column}", phase)] = df_result[("monitored_worktime_hour", phase)] / df_result[(column, phase)]
                    df_result[(f"actual_worktime_hour/{column}", phase)] = df_result[("actual_worktime_hour", phase)] / df_result[(column, phase)]

            phase = TaskPhase.ANNOTATION.value
            for column in production_volume_columns:
                df_result[(f"pointed_out_inspection_comment_count/{column}", phase)] = df_result[("pointed_out_inspection_comment_count", phase)] / df_result[(column, phase)]
            df_result[("rejected_count/task_count", phase)] = df_result[("rejected_count", phase)] / df_result[("task_count", phase)]

        df_result[(metadata_key, "")] = df_result.index
        df_result = df_result.reset_index(drop=True)
        result = cls(df_result, metadata_key, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)
        return result

    @classmethod
    def empty(cls, metadata_key: str, *, custom_production_volume_list: list[ProductionVolumeColumn] | None = None) -> TaskMetadataPerformance:
        """空のデータフレームを持つインスタンスを生成する。"""
        return cls(pandas.DataFrame(columns=pandas.MultiIndex.from_tuples([(metadata_key, "")])), metadata_key, custom_production_volume_list=custom_production_volume_list)

    def to_csv(self, output_file: Path) -> None:
        """CSVを出力する。"""
        logger.debug(f"{output_file!s} を出力します。")
        print_csv(self.df.reindex(columns=pandas.MultiIndex.from_tuples(self.columns)), output_file)
