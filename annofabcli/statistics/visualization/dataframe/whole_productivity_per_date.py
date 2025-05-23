# pylint: disable=too-many-lines
"""
全体の日ごとの生産性
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from annofabapi.models import TaskPhase, TaskStatus
from bokeh.models import DataRange1d
from bokeh.models.ui import UIElement
from bokeh.models.widgets.markups import Div
from bokeh.plotting import ColumnDataSource
from dateutil.parser import parse

from annofabcli.common.bokeh import create_pretext_from_metadata
from annofabcli.common.type_util import assert_noreturn
from annofabcli.common.utils import datetime_to_date, print_csv
from annofabcli.statistics.linegraph import (
    LineGraph,
    get_color_from_small_palette,
    get_weekly_moving_average,
    get_weekly_sum,
    write_bokeh_graph,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

logger = logging.getLogger(__name__)


WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX = "__lastweek"
"""1週間移動平均を表す列名のsuffix"""

SECONDARY_Y_RANGE_RATIO = 1.05
"""
第2のY軸の範囲の最大値を、値の最大値に対して何倍にするか
"""


def _plot_and_moving_average(
    line_graph: LineGraph,
    source: ColumnDataSource,
    x_column: str,
    y_column: str,
    legend_name: str,
    color: str,
    is_secondary_y_axis: bool = False,  # noqa: FBT001, FBT002
    **kwargs,  # noqa: ANN003
) -> None:
    """
    折れ線と1週間移動平均をプロットします。

    Args:
        fig ([type]): [description]
        y_column_name (str): [description]
        legend_name (str): [description]
        source ([type]): [description]
        color ([type]): [description]
    """

    # 値をプロット
    line_graph.add_line(
        source=source,
        x_column=x_column,
        y_column=y_column,
        color=color,
        legend_label=legend_name,
        is_secondary_y_axis=is_secondary_y_axis,
        **kwargs,
    )

    # 移動平均をプロット
    line_graph.add_moving_average_line(
        source=source,
        x_column=x_column,
        y_column=f"{y_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
        color=color,
        legend_label=f"{legend_name}の1週間移動平均",
        is_secondary_y_axis=is_secondary_y_axis,
        **kwargs,
    )


class WholeProductivityPerCompletedDate:
    """完了日ごとの全体の生産量と生産性に関する情報"""

    def __init__(
        self,
        df: pandas.DataFrame,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> None:
        self.df = df
        self.task_completion_criteria = task_completion_criteria
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_csv(
        cls,
        csv_file: Path,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> WholeProductivityPerCompletedDate:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file))
        return cls(df, task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    @staticmethod
    def _create_df_date(date_index1: pandas.Index, date_index2: pandas.Index) -> pandas.DataFrame:
        # 日付の一覧を生成
        if len(date_index1) > 0 and len(date_index2) > 0:
            start_date = min(date_index1[0], date_index2[0])
            end_date = max(date_index1[-1], date_index2[-1])
        elif len(date_index1) > 0 and len(date_index2) == 0:
            start_date = date_index1[0]
            end_date = date_index1[-1]
        elif len(date_index1) == 0 and len(date_index2) > 0:
            start_date = date_index2[0]
            end_date = date_index2[-1]
        else:
            return pandas.DataFrame()

        return pandas.DataFrame(index=[e.strftime("%Y-%m-%d") for e in pandas.date_range(start_date, end_date)])

    @classmethod
    def from_df_wrapper(cls, task: Task, worktime_per_date: WorktimePerDate, task_completion_criteria: TaskCompletionCriteria) -> WholeProductivityPerCompletedDate:
        """
        完了日毎の全体の生産量、生産性を算出する。

        Args:
            task: タスク情報が格納されたDataFrameをラップするクラスのインスタンス
            worktime_per_date: ユーザごと日ごとの作業時間が格納されたDataFrameをラップするクラスのインスタンス。以下の列を参照する
                date
                user_id
                actual_worktime_hour
                monitored_worktime_hour
                monitored_annotation_worktime_hour
                monitored_inspection_worktime_hour
                monitored_acceptance_worktime_hour
        """

        if task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            # 受入フェーズに到達したらタスクの作業が完了したとみなす場合、受入フェーズの作業時間や生産量は不要な情報なので、受入作業時間を0にする
            worktime_per_date = worktime_per_date.to_non_acceptance()

        # 生産量を表す列名
        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in task.custom_production_volume_list]]

        if task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_COMPLETED:
            datetime_column = "first_acceptance_completed_datetime"
        elif task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            datetime_column = "first_acceptance_reached_datetime"
        else:
            assert_noreturn(task_completion_criteria)

        df_sub_task = task.df[["task_id", datetime_column, *production_volume_columns]].copy()
        date_column = datetime_column.replace("_datetime", "_date")
        df_sub_task[date_column] = df_sub_task[datetime_column].map(lambda e: datetime_to_date(e) if not pandas.isna(e) else None)

        # 完了日を軸にして集計する
        df_agg_sub_task = df_sub_task.pivot_table(
            values=production_volume_columns,
            index=date_column,
            aggfunc="sum",
        ).fillna(0)
        if len(df_agg_sub_task) > 0:
            df_agg_sub_task["task_count"] = df_sub_task.pivot_table(values=["task_id"], index=date_column, aggfunc="count").fillna(0)
        else:
            # 列だけ作る
            df_agg_sub_task = df_agg_sub_task.assign(**dict.fromkeys(production_volume_columns, 0), task_count=0)

        df_worktime = worktime_per_date.df
        if len(df_worktime) > 0:
            df_agg_labor = df_worktime.pivot_table(
                values=[
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
                ],
                index="date",
                aggfunc="sum",
            ).fillna(0)

            # 作業したユーザ数を算出
            df_tmp = df_worktime[df_worktime["monitored_worktime_hour"] > 0].pivot_table(values=["user_id"], index="date", aggfunc="count").fillna(0)
            if len(df_tmp) > 0:
                df_agg_labor["working_user_count"] = df_tmp
            else:
                df_agg_labor["working_user_count"] = 0

            df_agg_labor["unmonitored_worktime_hour"] = df_agg_labor["actual_worktime_hour"] - df_agg_labor["monitored_worktime_hour"]

        else:
            df_agg_labor = pandas.DataFrame(
                columns=[
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
                    "unmonitored_worktime_hour",
                    "working_user_count",
                ],
                dtype="float",
                index=pandas.Index([], name="date", dtype="string"),
            )

        # 日付の一覧を生成
        df_date_base = cls._create_df_date(df_agg_sub_task.index, df_agg_labor.index)

        df_date = df_date_base.join(df_agg_sub_task).join(df_agg_labor).fillna(0)
        df_date["date"] = df_date.index

        cls._add_velocity_columns(df_date, production_volume_columns)
        return cls(df_date, task_completion_criteria, custom_production_volume_list=task.custom_production_volume_list)

    @classmethod
    def _add_velocity_columns(cls, df: pandas.DataFrame, production_volume_columns: list[str]) -> None:
        """
        生産性情報などの列を追加する。
        """

        def add_cumsum_column(df: pandas.DataFrame, column: str) -> None:
            """累積情報の列を追加"""
            df[f"cumsum_{column}"] = df[column].cumsum()

        def add_velocity_column(df: pandas.DataFrame, numerator_column: str, denominator_column: str) -> None:
            """速度情報の列を追加"""
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]
            # 1週間移動平均も出力
            df[f"{numerator_column}/{denominator_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df[numerator_column]) / get_weekly_sum(df[denominator_column])

        # 累計情報を追加
        add_cumsum_column(df, column="task_count")
        add_cumsum_column(df, column="input_data_count")
        add_cumsum_column(df, column="actual_worktime_hour")
        add_cumsum_column(df, column="monitored_worktime_hour")

        # 生産性情報を追加
        for category in ["actual", "monitored"]:
            for unit in ["task_count", *production_volume_columns]:
                add_velocity_column(df, numerator_column=f"{category}_worktime_hour", denominator_column=unit)

        # フェーズごとの作業時間は、細かい単位で生産性を出したいので、task_countを使わない
        for category in ["monitored_annotation", "monitored_inspection", "monitored_acceptance", "unmonitored"]:
            for unit in production_volume_columns:
                add_velocity_column(df, numerator_column=f"{category}_worktime_hour", denominator_column=unit)

    def _create_div_element(self) -> Div:
        """
        HTMLページの先頭に付与するdiv要素を生成する。
        """
        if self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_COMPLETED:
            str_task = "受入フェーズ完了状態"
        elif self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            str_task = "受入フェーズ"
        else:
            assert_noreturn(self.task_completion_criteria)

        elm_list = ["<h4>注意</h4>", f"<p>「X日のタスク数」は、X日に初めて{str_task}になったタスクの個数です。</p>"]
        if self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            elm_list.append("<p>タスクが受入フェーズに到達したら作業が完了したとみなしているため、受入作業時間は0にしています。</p>")
        return Div(text=" ".join(elm_list))

    def plot(
        self,
        output_file: Path,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        全体の生産量や生産性をプロットする
        """

        def add_velocity_columns(df: pandas.DataFrame) -> None:
            for denominator in [e.value for e in production_volume_list]:
                for category in [
                    "actual",
                    "monitored",
                    "monitored_annotation",
                    "monitored_inspection",
                    "monitored_acceptance",
                    "unmonitored",
                ]:
                    df[f"{category}_worktime_minute/{denominator}"] = df[f"{category}_worktime_hour"] * 60 / df[denominator]
                    df[f"{category}_worktime_minute/{denominator}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df[f"{category}_worktime_hour"]) * 60 / get_weekly_sum(df[denominator])

            df[f"actual_worktime_hour/task_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df["actual_worktime_hour"]) / get_weekly_sum(df["task_count"])
            df[f"monitored_worktime_hour/task_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df["monitored_worktime_hour"]) / get_weekly_sum(df["task_count"])

            for column in [
                "task_count",
                "input_data_count",
                "actual_worktime_hour",
                "monitored_worktime_hour",
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
                "unmonitored_worktime_hour",
            ]:
                df[f"{column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_moving_average(df[column])

        def create_line_graph(title: str, y_axis_label: str, tooltip_columns: list[str]) -> LineGraph:
            return LineGraph(
                width=1200,
                height=600,
                title=title,
                x_axis_label="日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
                tooltip_columns=tooltip_columns,
            )

        def create_task_line_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="日ごとのタスク数と作業時間",
                y_axis_label="タスク数",
                tooltip_columns=["date", "task_count", "actual_worktime_hour", "monitored_worktime_hour", "working_user_count"],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[時間]",
                secondary_y_axis_range=DataRange1d(end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max()) * SECONDARY_Y_RANGE_RATIO),
                primary_y_axis_range=DataRange1d(end=df["task_count"].max() * SECONDARY_Y_RANGE_RATIO),
            )

            plot_index = 0
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="task_count",
                legend_name="タスク数",
                color=get_color_from_small_palette(plot_index),
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="actual_worktime_hour",
                legend_name="実績作業時間",
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="monitored_worktime_hour",
                legend_name="計測作業時間",
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )
            return line_graph

        def create_input_data_line_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="日ごとの入力データ数と作業時間",
                y_axis_label="入力データ数",
                tooltip_columns=["date", "input_data_count", "actual_worktime_hour", "monitored_worktime_hour", "working_user_count"],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[時間]",
                secondary_y_axis_range=DataRange1d(end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max()) * SECONDARY_Y_RANGE_RATIO),
                primary_y_axis_range=DataRange1d(end=df["input_data_count"].max() * SECONDARY_Y_RANGE_RATIO),
            )

            plot_index = 0
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="input_data_count",
                legend_name="入力データ数",
                color=get_color_from_small_palette(plot_index),
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="actual_worktime_hour",
                legend_name="実績作業時間",
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                source=source,
                x_column="dt_date",
                y_column="monitored_worktime_hour",
                legend_name="計測作業時間",
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )

            return line_graph

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()
        df["dt_date"] = df["date"].map(lambda e: parse(e).date())

        production_volume_list = [
            ProductionVolumeColumn("input_data_count", "入力データ"),
            ProductionVolumeColumn("annotation_count", "アノテーション"),
            *self.custom_production_volume_list,
        ]

        add_velocity_columns(df)

        logger.debug(f"{output_file} を出力します。")

        phase_prefix = [
            ("actual_worktime", "実績作業時間"),
            ("monitored_worktime", "計測作業時間"),
            ("monitored_annotation_worktime", "計測作業時間(教師付)"),
            ("monitored_inspection_worktime", "計測作業時間(検査)"),
            ("monitored_acceptance_worktime", "計測作業時間(受入)"),
        ]
        if df["actual_worktime_hour"].sum() > 0:
            # 条件分岐の理由：実績作業時間がないときは、非計測作業時間がマイナス値になり、分かりづらいグラフになるため。必要なときのみ非計測作業時間をプロットする
            phase_prefix.append(("unmonitored_worktime", "非計測作業時間"))

        fig_info_list = [
            {
                "line_graph": create_line_graph(
                    title="日ごとの作業時間",
                    y_axis_label="作業時間[時間]",
                    tooltip_columns=[
                        "date",
                        "actual_worktime_hour",
                        "monitored_worktime_hour",
                        "monitored_annotation_worktime_hour",
                        "monitored_inspection_worktime_hour",
                        "monitored_acceptance_worktime_hour",
                        "working_user_count",
                    ],
                ),
                "y_info_list": [{"column": f"{e[0]}_hour", "legend": f"{e[1]}"} for e in phase_prefix],
            },
        ]

        for info in production_volume_list:
            fig_info_list.append(  # noqa: PERF401
                {
                    "line_graph": create_line_graph(
                        title=f"日ごとの{info.name}あたり作業時間",
                        y_axis_label=f"{info.name}あたり作業時間[分/{info.name}]",
                        tooltip_columns=[
                            "date",
                            info.value,
                            "actual_worktime_hour",
                            "monitored_worktime_hour",
                            "monitored_annotation_worktime_hour",
                            "monitored_inspection_worktime_hour",
                            "monitored_acceptance_worktime_hour",
                            f"actual_worktime_minute/{info.value}",
                            f"monitored_worktime_minute/{info.value}",
                            f"monitored_annotation_worktime_minute/{info.value}",
                            f"monitored_inspection_worktime_minute/{info.value}",
                            f"monitored_acceptance_worktime_minute/{info.value}",
                        ],
                    ),
                    "y_info_list": [{"column": f"{e[0]}_minute/{info.value}", "legend": f"{info.name}あたり{e[1]}"} for e in phase_prefix],
                }
            )

        source = ColumnDataSource(data=df)

        for fig_info in fig_info_list:
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore[assignment]
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)
                line_graph: LineGraph = fig_info["line_graph"]  # type: ignore[assignment]
                _plot_and_moving_average(
                    line_graph=line_graph,
                    x_column="dt_date",
                    y_column=y_info["column"],
                    legend_name=y_info["legend"],
                    source=source,
                    color=color,
                )

        line_graph_list = [
            create_task_line_graph(),
            create_input_data_line_graph(),
        ]
        line_graph_list.extend([info["line_graph"] for info in fig_info_list])  # type: ignore[misc]

        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

        div_element = self._create_div_element()
        element_list: list[UIElement] = [div_element] + [e.figure for e in line_graph_list]
        if metadata is not None:
            element_list.insert(0, create_pretext_from_metadata(metadata))

        write_bokeh_graph(bokeh.layouts.column(element_list), output_file)

    def plot_cumulatively(self, output_file: Path, *, metadata: Optional[dict[str, Any]] = None) -> None:
        """
        全体の生産量や作業時間の累積折れ線グラフを出力する
        """

        def create_line_graph(title: str, y_axis_label: str, tooltip_columns: list[str]) -> LineGraph:
            return LineGraph(
                width=1200,
                height=600,
                title=title,
                x_axis_label="日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
                tooltip_columns=tooltip_columns,
            )

        def create_task_line_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="日ごとの累積タスク数と累積作業時間",
                y_axis_label="タスク数",
                tooltip_columns=[
                    "date",
                    "task_count",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "working_user_count",
                    "cumsum_task_count",
                    "cumsum_actual_worktime_hour",
                    "cumsum_monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[時間]",
                secondary_y_axis_range=DataRange1d(end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max()) * SECONDARY_Y_RANGE_RATIO),
                primary_y_axis_range=DataRange1d(end=df["cumsum_task_count"].max() * SECONDARY_Y_RANGE_RATIO),
            )

            # 値をプロット
            x_column = "dt_date"
            plot_index = 0
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_task_count",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="タスク数",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_actual_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="実績作業時間",
                is_secondary_y_axis=True,
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間",
                is_secondary_y_axis=True,
            )

            return line_graph

        def create_input_data_line_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="日ごとの累積入力データ数と累積作業時間",
                y_axis_label="入力データ数",
                tooltip_columns=[
                    "date",
                    "input_data_count",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "working_user_count",
                    "cumsum_input_data_count",
                    "cumsum_actual_worktime_hour",
                    "cumsum_monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[時間]",
                secondary_y_axis_range=DataRange1d(end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max()) * SECONDARY_Y_RANGE_RATIO),
                primary_y_axis_range=DataRange1d(end=df["cumsum_input_data_count"].max() * SECONDARY_Y_RANGE_RATIO),
            )

            x_column = "dt_date"
            plot_index = 0
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_input_data_count",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="タスク数",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_actual_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="実績作業時間",
                is_secondary_y_axis=True,
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間",
                is_secondary_y_axis=True,
            )
            return line_graph

        def create_worktime_line_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="日ごとの累積作業時間",
                y_axis_label="作業時間[時間]",
                tooltip_columns=[
                    "date",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
                    "working_user_count",
                    "cumsum_actual_worktime_hour",
                    "cumsum_monitored_worktime_hour",
                    "cumsum_monitored_annotation_worktime_hour",
                    "cumsum_monitored_inspection_worktime_hour",
                    "cumsum_monitored_acceptance_worktime_hour",
                ],
            )

            # 値をプロット
            x_column = "dt_date"
            plot_index = 0
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_actual_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="実績作業時間",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_annotation_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間(教師付)",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_inspection_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間(検査)",
            )

            plot_index += 1
            line_graph.add_line(
                x_column=x_column,
                y_column="cumsum_monitored_acceptance_worktime_hour",
                source=source,
                color=get_color_from_small_palette(plot_index),
                legend_label="計測作業時間(受入)",
            )

            return line_graph

        if not self._validate_df_for_output(output_file):
            return

        df = self.df.copy()
        df["dt_date"] = df["date"].map(lambda e: parse(e).date())

        df["cumsum_monitored_annotation_worktime_hour"] = df["monitored_annotation_worktime_hour"].cumsum()
        df["cumsum_monitored_inspection_worktime_hour"] = df["monitored_inspection_worktime_hour"].cumsum()
        df["cumsum_monitored_acceptance_worktime_hour"] = df["monitored_acceptance_worktime_hour"].cumsum()

        logger.debug(f"{output_file} を出力します。")

        source = ColumnDataSource(data=df)

        line_graph_list = [create_task_line_graph(), create_input_data_line_graph(), create_worktime_line_graph()]

        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

        div_element = self._create_div_element()

        element_list: list[UIElement] = [div_element] + [e.figure for e in line_graph_list]
        if metadata is not None:
            element_list.insert(0, create_pretext_from_metadata(metadata))

        write_bokeh_graph(bokeh.layouts.column(element_list), output_file)

    @classmethod
    def empty(cls, *, task_completion_criteria: TaskCompletionCriteria, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> WholeProductivityPerCompletedDate:
        df = pandas.DataFrame(columns=cls.get_columns(custom_production_volume_list=custom_production_volume_list))
        return cls(df, task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    @property
    def columns(self) -> list[str]:
        return self.get_columns(custom_production_volume_list=self.custom_production_volume_list)

    @staticmethod
    def get_columns(custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> list[str]:
        production_volume_columns = ["input_data_count", "annotation_count"]
        if custom_production_volume_list is not None:
            production_volume_columns.extend([e.value for e in custom_production_volume_list])

        worktime_columns = [
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "monitored_annotation_worktime_hour",
            "monitored_inspection_worktime_hour",
            "monitored_acceptance_worktime_hour",
            "unmonitored_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for suffix in ["", WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX]
            for numerator in ["actual_worktime_hour", "monitored_worktime_hour"]
            for denominator in ["task_count", *production_volume_columns]
        ]

        # フェーズごとの作業時間に関する生産性
        velocity_details_columns = [
            f"{numerator}/{denominator}{suffix}"
            for suffix in ["", WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX]
            for numerator in [
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
                "unmonitored_worktime_hour",
            ]
            for denominator in production_volume_columns
        ]

        columns = [
            "date",
            "cumsum_task_count",
            "cumsum_input_data_count",
            "cumsum_actual_worktime_hour",
            "cumsum_monitored_worktime_hour",
            "task_count",
            *production_volume_columns,
            *worktime_columns,
            *velocity_columns,
            *velocity_details_columns,
            "working_user_count",
        ]
        return columns

    def to_csv(self, output_file: Path) -> None:
        """
        日毎の全体の生産量、生産性を出力する。

        """
        if not self._validate_df_for_output(output_file):
            return

        print_csv(self.df[self.columns], output=str(output_file))


class WholeProductivityPerFirstAnnotationStartedDate:
    """教師付開始日ごとの全体の生産量と生産性に関する情報"""

    def __init__(
        self,
        df: pandas.DataFrame,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> None:
        self.task_completion_criteria = task_completion_criteria
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []
        self.df = df

    @classmethod
    def from_csv(
        cls,
        csv_file: Path,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> WholeProductivityPerFirstAnnotationStartedDate:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file))
        return cls(df, task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def _add_velocity_columns(cls, df: pandas.DataFrame, production_volume_columns: list[str]) -> None:
        """
        日毎の全体の生産量から、累計情報、生産性の列を追加する。
        """

        def add_velocity_column(df: pandas.DataFrame, numerator_column: str, denominator_column: str) -> None:
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]

            df[f"{numerator_column}/{denominator_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_moving_average(df[numerator_column]) / get_weekly_moving_average(df[denominator_column])

        # annofab 計測時間から算出したvelocityを追加
        for column in production_volume_columns:
            add_velocity_column(df, numerator_column="worktime_hour", denominator_column=column)
            add_velocity_column(df, numerator_column="annotation_worktime_hour", denominator_column=column)
            add_velocity_column(df, numerator_column="inspection_worktime_hour", denominator_column=column)
            add_velocity_column(df, numerator_column="acceptance_worktime_hour", denominator_column=column)

    @classmethod
    def from_task(cls, task: Task, task_completion_criteria: TaskCompletionCriteria) -> WholeProductivityPerFirstAnnotationStartedDate:
        # 生産量を表す列名
        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in task.custom_production_volume_list]]

        if task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            # 受入フェーズに到達したらタスクの作業が完了したとみなす場合、受入フェーズの作業時間や生産量は不要な情報なので、受入作業時間を0にする
            task = task.to_non_acceptance()

        df_task = task.df
        if task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_COMPLETED:
            df_sub_task = df_task[df_task["status"] == TaskStatus.COMPLETE.value]
        elif task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            df_sub_task = df_task[df_task["phase"] == TaskPhase.ACCEPTANCE.value]
        else:
            assert_noreturn(task_completion_criteria)

        df_sub_task = df_sub_task[
            [
                "task_id",
                "first_annotation_started_datetime",
                *production_volume_columns,
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        ].copy()
        df_sub_task["first_annotation_started_date"] = df_sub_task["first_annotation_started_datetime"].map(lambda e: datetime_to_date(e) if not pandas.isna(e) else None)

        value_columns = [
            *production_volume_columns,
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]
        df_agg_sub_task = df_sub_task.pivot_table(
            values=value_columns,
            index="first_annotation_started_date",
            aggfunc="sum",
        ).fillna(0)
        if len(df_agg_sub_task) > 0:
            df_agg_sub_task["task_count"] = df_sub_task.pivot_table(values=["task_id"], index="first_annotation_started_date", aggfunc="count").fillna(0)
        else:
            # 列だけ作る
            df_agg_sub_task = df_agg_sub_task.assign(**dict.fromkeys(value_columns, 0), task_count=0)

        # 日付の一覧を生成
        if len(df_agg_sub_task) > 0:
            df_date_base = pandas.DataFrame(index=[e.strftime("%Y-%m-%d") for e in pandas.date_range(start=df_agg_sub_task.index.min(), end=df_agg_sub_task.index.max())])
        else:
            df_date_base = pandas.DataFrame()

        df_date = df_date_base.join(df_agg_sub_task).fillna(0)

        df_date["first_annotation_started_date"] = df_date.index
        # 生産性情報などの列を追加する
        cls._add_velocity_columns(df_date, production_volume_columns)
        return cls(df_date, task_completion_criteria, custom_production_volume_list=task.custom_production_volume_list)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def empty(cls, task_completion_criteria: TaskCompletionCriteria, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> WholeProductivityPerFirstAnnotationStartedDate:
        df = pandas.DataFrame(columns=cls.get_columns(custom_production_volume_list=custom_production_volume_list))
        return cls(df, task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    @staticmethod
    def get_columns(*, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> list[str]:
        production_volume_columns = ["input_data_count", "annotation_count"]
        if custom_production_volume_list is not None:
            production_volume_columns.extend([e.value for e in custom_production_volume_list])

        basic_columns = [
            "first_annotation_started_date",
            "task_count",
            *production_volume_columns,
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for suffix in ["", WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX]
            for denominator in production_volume_columns
            for numerator in [
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        ]
        columns = basic_columns + velocity_columns
        return columns

    @property
    def columns(self) -> list[str]:
        return self.get_columns(custom_production_volume_list=self.custom_production_volume_list)

    def to_csv(self, output_file: Path) -> pandas.DataFrame:
        if not self._validate_df_for_output(output_file):
            return

        print_csv(self.df[self.columns], str(output_file))

    def plot(self, output_file: Path, *, metadata: Optional[dict[str, Any]] = None) -> None:  # noqa: PLR0915
        """
        全体の生産量や生産性をプロットする
        """

        def add_velocity_and_weekly_moving_average_columns(df: pandas.DataFrame) -> None:
            for column in [
                "task_count",
                "input_data_count",
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]:
                df[f"{column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_moving_average(df[column])

            for denominator in [e.value for e in production_volume_list]:
                for numerator in ["worktime", "annotation_worktime", "inspection_worktime", "acceptance_worktime"]:
                    df[f"{numerator}_minute/{denominator}"] = df[f"{numerator}_hour"] * 60 / df[denominator]
                    df[f"{numerator}_minute/{denominator}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(df[f"{numerator}_hour"]) * 60 / get_weekly_sum(df[denominator])

        def create_div_element() -> Div:
            """
            HTMLページの先頭に付与するdiv要素を生成する。
            """
            if self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_COMPLETED:
                str_task = "受入フェーズ完了状態"
            elif self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
                str_task = "受入フェーズ"
            else:
                assert_noreturn(self.task_completion_criteria)

            elm_list = ["<h4>注意</h4>", f"<p>「X日のタスク数」は、X日に教師付フェーズを開始したタスクの内、{str_task}であるタスクの個数です。</p>"]
            if self.task_completion_criteria == TaskCompletionCriteria.ACCEPTANCE_REACHED:
                elm_list.append("<p>タスクが受入フェーズに到達したら作業が完了したとみなしているため、受入作業時間は0にしています。</p>")

            return Div(text=" ".join(elm_list))

        def create_line_graph(title: str, y_axis_label: str, tooltip_columns: list[str]) -> LineGraph:
            return LineGraph(
                width=1200,
                height=600,
                title=title,
                x_axis_label="教師付開始日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
                tooltip_columns=tooltip_columns,
            )

        def create_task_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="教師付開始日ごとのタスク数と計測作業時間",
                y_axis_label="タスク数",
                tooltip_columns=[
                    "first_annotation_started_date",
                    "task_count",
                    "worktime_hour",
                ],
            )

            line_graph.add_secondary_y_axis(
                "作業時間[時間]",
                secondary_y_axis_range=DataRange1d(end=df["worktime_hour"].max() * SECONDARY_Y_RANGE_RATIO),
                primary_y_axis_range=DataRange1d(end=df["task_count"].max() * SECONDARY_Y_RANGE_RATIO),
            )

            plot_index = 0
            _plot_and_moving_average(
                line_graph,
                x_column="dt_first_annotation_started_date",
                y_column="task_count",
                legend_name="タスク数",
                source=source,
                color=get_color_from_small_palette(plot_index),
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                x_column="dt_first_annotation_started_date",
                y_column="worktime_hour",
                legend_name="計測作業時間",
                source=source,
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )
            return line_graph

        def create_input_data_graph() -> LineGraph:
            line_graph = create_line_graph(
                title="教師付開始日ごとの入力データ数と計測作業時間",
                y_axis_label="入力データ数",
                tooltip_columns=[
                    "first_annotation_started_date",
                    "input_data_count",
                    "worktime_hour",
                ],
            )

            line_graph.add_secondary_y_axis("作業時間[時間]")

            plot_index = 0
            _plot_and_moving_average(
                line_graph,
                x_column="dt_first_annotation_started_date",
                y_column="input_data_count",
                legend_name="入力データ数",
                source=source,
                color=get_color_from_small_palette(plot_index),
            )

            plot_index += 1
            _plot_and_moving_average(
                line_graph,
                x_column="dt_first_annotation_started_date",
                y_column="worktime_hour",
                legend_name="計測作業時間",
                source=source,
                color=get_color_from_small_palette(plot_index),
                is_secondary_y_axis=True,
            )
            return line_graph

        if not self._validate_df_for_output(output_file):
            return

        production_volume_list = [
            ProductionVolumeColumn("input_data_count", "入力データ"),
            ProductionVolumeColumn("annotation_count", "アノテーション"),
            *self.custom_production_volume_list,
        ]

        df = self.df.copy()
        df["dt_first_annotation_started_date"] = df["first_annotation_started_date"].map(lambda e: parse(e).date())
        add_velocity_and_weekly_moving_average_columns(df)

        logger.debug(f"{output_file} を出力します。")

        @dataclass
        class LegendInfo:
            column: str
            legend: str

        @dataclass
        class GraphInfo:
            line_graph: LineGraph
            y_info_list: list[LegendInfo]

        graph_info_list = [
            GraphInfo(
                line_graph=create_line_graph(
                    title="教師付開始日ごとの計測作業時間",
                    y_axis_label="作業時間[時間]",
                    tooltip_columns=[
                        "first_annotation_started_date",
                        "worktime_hour",
                        "annotation_worktime_hour",
                        "inspection_worktime_hour",
                        "acceptance_worktime_hour",
                    ],
                ),
                y_info_list=[
                    LegendInfo("worktime_hour", "計測作業時間"),
                    LegendInfo("annotation_worktime_hour", "計測作業時間(教師付)"),
                    LegendInfo("inspection_worktime_hour", "計測作業時間(検査)"),
                    LegendInfo("acceptance_worktime_hour", "計測作業時間(受入)"),
                ],
            )
        ]
        for info in production_volume_list:
            graph_info_list.append(  # noqa: PERF401
                GraphInfo(
                    line_graph=create_line_graph(
                        title=f"教師付開始日ごとの{info.name}あたり計測作業時間",
                        y_axis_label=f"{info.name}あたり作業時間[分/{info.name}]",
                        tooltip_columns=[
                            "first_annotation_started_date",
                            info.value,
                            "worktime_hour",
                            "annotation_worktime_hour",
                            "inspection_worktime_hour",
                            "acceptance_worktime_hour",
                            f"worktime_minute/{info.value}",
                            f"annotation_worktime_minute/{info.value}",
                            f"inspection_worktime_minute/{info.value}",
                            f"acceptance_worktime_minute/{info.value}",
                        ],
                    ),
                    y_info_list=[
                        LegendInfo(f"worktime_minute/{info.value}", f"{info.name}あたり計測作業時間"),
                        LegendInfo(f"annotation_worktime_minute/{info.value}", f"{info.name}あたり計測作業時間(教師付)"),
                        LegendInfo(f"inspection_worktime_minute/{info.value}", f"{info.name}あたり計測作業時間(検査)"),
                        LegendInfo(f"acceptance_worktime_minute/{info.value}", f"{info.name}あたり計測作業時間(受入)"),
                    ],
                )
            )

        source = ColumnDataSource(data=df)

        for graph_info in graph_info_list:
            y_info_list = graph_info.y_info_list
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)

                _plot_and_moving_average(
                    graph_info.line_graph,
                    x_column="dt_first_annotation_started_date",
                    y_column=y_info.column,
                    legend_name=y_info.legend,
                    source=source,
                    color=color,
                )

        line_graph_list = [create_task_graph(), create_input_data_graph(), *[e.line_graph for e in graph_info_list]]

        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

        element_list: list[UIElement] = [create_div_element()] + [e.figure for e in line_graph_list]
        if metadata is not None:
            element_list.insert(0, create_pretext_from_metadata(metadata))

        write_bokeh_graph(bokeh.layouts.column(element_list), output_file)
