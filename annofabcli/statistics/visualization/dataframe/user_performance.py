"""
各ユーザの合計の生産性と品質
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy
import pandas
from annofabapi.models import TaskPhase

from annofabcli.common.utils import print_csv
import copy


logger = logging.getLogger(__name__)



class UserPerformance:
    """
    各ユーザの合計の生産性と品質

    """

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 600

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    @staticmethod
    def _add_ratio_column_for_productivity_per_user(df: pandas.DataFrame, phase_list: list[str]):
        for phase in phase_list:
            # AnnoFab時間の比率
            df[("monitored_worktime_ratio", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("monitored_worktime_hour", "sum")]
            )
            # AnnoFab時間の比率から、Annowork時間を予測する
            df[("prediction_actual_worktime_hour", phase)] = (
                df[("actual_worktime_hour", "sum")] * df[("monitored_worktime_ratio", phase)]
            )

            # 生産性を算出
            df[("monitored_worktime/input_data_count", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("input_data_count", phase)]
            )
            df[("actual_worktime/input_data_count", phase)] = (
                df[("prediction_actual_worktime_hour", phase)] / df[("input_data_count", phase)]
            )

            df[("monitored_worktime/annotation_count", phase)] = (
                df[("monitored_worktime_hour", phase)] / df[("annotation_count", phase)]
            )
            df[("actual_worktime/annotation_count", phase)] = (
                df[("prediction_actual_worktime_hour", phase)] / df[("annotation_count", phase)]
            )

        phase = TaskPhase.ANNOTATION.value
        df[("pointed_out_inspection_comment_count/annotation_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("annotation_count", phase)]
        )
        df[("pointed_out_inspection_comment_count/input_data_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("input_data_count", phase)]
        )
        df[("rejected_count/task_count", phase)] = df[("rejected_count", phase)] / df[("task_count", phase)]

    @staticmethod
    def _get_phase_list(columns: list[str]) -> list[str]:
        phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        if TaskPhase.INSPECTION.value not in columns:
            phase_list.remove(TaskPhase.INSPECTION.value)

        if TaskPhase.ACCEPTANCE.value not in columns:
            phase_list.remove(TaskPhase.ACCEPTANCE.value)

        return phase_list

    @classmethod
    def from_df(
        cls, df_task_history: pandas.DataFrame, df_labor: pandas.DataFrame, df_worktime_ratio: pandas.DataFrame
    ) -> UserPerformance:
        """
        AnnoWorkの実績時間から、作業者ごとに生産性を算出する。

        Args:
            df_task_history: タスク履歴のDataFrame
            df_labor: 実績作業時間のDataFrame
            df_worktime_ratio: 作業したタスク数を、作業時間で按分した値が格納されたDataFrame

        Returns:

        """
        df_agg_task_history = df_task_history.pivot_table(
            values="worktime_hour", columns="phase", index="user_id", aggfunc=numpy.sum
        ).fillna(0)

        if len(df_labor) > 0:
            df_agg_labor = df_labor.pivot_table(values="actual_worktime_hour", index="user_id", aggfunc=numpy.sum)
            df_tmp = df_labor[df_labor["actual_worktime_hour"] > 0].pivot_table(
                values="date", index="user_id", aggfunc=numpy.max
            )
            if len(df_tmp) > 0:
                df_agg_labor["last_working_date"] = df_tmp
            else:
                df_agg_labor["last_working_date"] = numpy.nan
            df = df_agg_task_history.join(df_agg_labor)
        else:
            df = df_agg_task_history
            df["actual_worktime_hour"] = 0
            df["last_working_date"] = None

        phase_list = cls._get_phase_list(list(df.columns))

        df = df[["actual_worktime_hour", "last_working_date"] + phase_list].copy()
        df.columns = pandas.MultiIndex.from_tuples(
            [("actual_worktime_hour", "sum"), ("last_working_date", "")]
            + [("monitored_worktime_hour", phase) for phase in phase_list]
        )

        df[("monitored_worktime_hour", "sum")] = df[[("monitored_worktime_hour", phase) for phase in phase_list]].sum(
            axis=1
        )

        df_agg_production = df_worktime_ratio.pivot_table(
            values=[
                "worktime_ratio_by_task",
                "input_data_count",
                "annotation_count",
                "pointed_out_inspection_comment_count",
                "rejected_count",
            ],
            columns="phase",
            index="user_id",
            aggfunc=numpy.sum,
        ).fillna(0)

        df_agg_production.rename(columns={"worktime_ratio_by_task": "task_count"}, inplace=True)
        df = df.join(df_agg_production)

        # 比例関係の列を計算して追加する
        cls._add_ratio_column_for_productivity_per_user(df, phase_list=phase_list)

        # 不要な列を削除する
        tmp_phase_list = copy.deepcopy(phase_list)
        tmp_phase_list.remove(TaskPhase.ANNOTATION.value)

        dropped_column = [("pointed_out_inspection_comment_count", phase) for phase in tmp_phase_list] + [
            ("rejected_count", phase) for phase in tmp_phase_list
        ]
        df = df.drop(dropped_column, axis=1)

        # ユーザ情報を取得
        df_user = df_task_history.groupby("user_id").first()[["username", "biography"]]
        df_user.columns = pandas.MultiIndex.from_tuples([("username", ""), ("biography", "")])
        df = df.join(df_user)
        df[("user_id", "")] = df.index

        return cls(df)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    def to_csv(self, output_file: Path) -> None:

        if not self._validate_df_for_output(output_file):
            return

        production_columns = [
            "first_annotation_started_date",
            "first_annotation_user_id",
            "first_annotation_username",
            "task_count",
            "input_data_count",
            "annotation_count",
            "inspection_count",
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}"
            for numerator in ["annotation_worktime_hour", "inspection_worktime_hour", "acceptance_worktime_hour"]
            for denominator in ["input_data_count", "annotation_count"]
        ]

        columns = (
            production_columns
            + velocity_columns
            + ["inspection_count/input_data_count", "inspection_count/annotation_count"]
        )

        print_csv(self.df[columns], output=str(output_file))
