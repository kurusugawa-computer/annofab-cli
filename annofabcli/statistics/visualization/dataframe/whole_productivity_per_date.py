# pylint: disable=too-many-lines
"""
全体の日ごとの生産性
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
from annofabapi.models import TaskStatus
from bokeh.models import DataRange1d
from bokeh.plotting import ColumnDataSource
from dateutil.parser import parse

from annofabcli.common.utils import datetime_to_date, print_csv
from annofabcli.statistics.linegraph import (
    LineGraph,
    get_color_from_small_palette,
    get_weekly_moving_average,
    get_weekly_sum,
    write_bokeh_graph,
)

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
    color,
    is_secondary_y_axis: bool = False,
    **kwargs,
):
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
    """受入完了日ごとの全体の生産量と生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_csv(cls, csv_file: Path) -> WholeProductivityPerCompletedDate:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file))
        return cls(df)

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
    def from_df(cls, df_task: pandas.DataFrame, df_worktime: pandas.DataFrame) -> WholeProductivityPerCompletedDate:
        """
        受入完了日毎の全体の生産量、生産性を算出する。

        Args:
            df_task: タスク情報が格納されたDataFrame
            df_worktime: ユーザごと日ごとの作業時間が格納されたDataFrame。以下の列を参照する
                date
                user_id
                actual_worktime_hour
                monitored_worktime_hour
                monitored_annotation_worktime_hour
                monitored_inspection_worktime_hour
                monitored_acceptance_worktime_hour
        """
        print(f"{df_task.columns=}")
        df_sub_task = df_task[
            [
                "task_id",
                "first_acceptance_completed_datetime",
                "input_data_count",
                "annotation_count",
            ]
        ].copy()
        df_sub_task["first_acceptance_completed_date"] = df_sub_task["first_acceptance_completed_datetime"].map(
            lambda e: datetime_to_date(e) if not pandas.isna(e) else None
        )

        # タスク完了日を軸にして集計する
        value_columns = [
            "input_data_count",
            "annotation_count",
        ]
        df_agg_sub_task = df_sub_task.pivot_table(
            values=value_columns,
            index="first_acceptance_completed_date",
            aggfunc=numpy.sum,
        ).fillna(0)
        if len(df_agg_sub_task) > 0:
            df_agg_sub_task["task_count"] = df_sub_task.pivot_table(
                values=["task_id"], index="first_acceptance_completed_date", aggfunc="count"
            ).fillna(0)
        else:
            # 列だけ作る
            df_agg_sub_task = df_agg_sub_task.assign(**{key: 0 for key in value_columns}, task_count=0)

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
                aggfunc=numpy.sum,
            ).fillna(0)

            # 作業したユーザ数を算出
            df_tmp = (
                df_worktime[df_worktime["monitored_worktime_hour"] > 0]
                .pivot_table(values=["user_id"], index="date", aggfunc="count")
                .fillna(0)
            )
            if len(df_tmp) > 0:
                df_agg_labor["working_user_count"] = df_tmp
            else:
                df_agg_labor["working_user_count"] = 0

            df_agg_labor["unmonitored_worktime_hour"] = (
                df_agg_labor["actual_worktime_hour"] - df_agg_labor["monitored_worktime_hour"]
            )

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
                ]
            )

        # 日付の一覧を生成
        df_date_base = cls._create_df_date(df_agg_sub_task.index, df_agg_labor.index)
        df_date = df_date_base.join(df_agg_sub_task).join(df_agg_labor).fillna(0)
        df_date["date"] = df_date.index

        cls._add_velocity_columns(df_date)
        return cls(df_date)

    @classmethod
    def _add_velocity_columns(cls, df: pandas.DataFrame):
        """
        生産性情報などの列を追加する。
        """

        def add_cumsum_column(df: pandas.DataFrame, column: str):
            """累積情報の列を追加"""
            df[f"cumsum_{column}"] = df[column].cumsum()

        def add_velocity_column(df: pandas.DataFrame, numerator_column: str, denominator_column: str):
            """速度情報の列を追加"""
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]
            # 1週間移動平均も出力
            df[f"{numerator_column}/{denominator_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(
                df[numerator_column]
            ) / get_weekly_sum(df[denominator_column])

        # 累計情報を追加
        add_cumsum_column(df, column="task_count")
        add_cumsum_column(df, column="input_data_count")
        add_cumsum_column(df, column="actual_worktime_hour")
        add_cumsum_column(df, column="monitored_worktime_hour")

        # 生産性情報を追加
        for category in ["actual", "monitored"]:
            for unit in ["task_count", "input_data_count", "annotation_count"]:
                add_velocity_column(df, numerator_column=f"{category}_worktime_hour", denominator_column=unit)

        # フェーズごとの作業時間は、細かい単位で生産性を出したいので、task_countを使わない
        for category in ["monitored_annotation", "monitored_inspection", "monitored_acceptance", "unmonitored"]:
            for unit in ["input_data_count", "annotation_count"]:
                add_velocity_column(df, numerator_column=f"{category}_worktime_hour", denominator_column=unit)

    @classmethod
    def merge(
        cls, obj1: WholeProductivityPerCompletedDate, obj2: WholeProductivityPerCompletedDate
    ) -> WholeProductivityPerCompletedDate:
        """
        日毎の全体の生産量、生産性が格納されたDataFrameを結合する。

        Args:
            df1:
            df2:

        Returns:
            マージ済のユーザごとの生産性・品質情報
        """
        df1 = obj1.df
        df2 = obj2.df

        def merge_row(
            str_date: str, columns: pandas.Index, row1: Optional[pandas.Series], row2: Optional[pandas.Series]
        ) -> pandas.Series:
            if row1 is not None and row2 is not None:
                sum_row = row1.fillna(0) + row2.fillna(0)
            elif row1 is not None and row2 is None:
                sum_row = row1.fillna(0)
            elif row1 is None and row2 is not None:
                sum_row = row2.fillna(0)
            else:
                sum_row = pandas.Series(index=columns)

            sum_row.name = str_date
            return sum_row

        def date_range():
            lower_date = min(df1["date"].min(), df2["date"].min())
            upper_date = max(df1["date"].max(), df2["date"].max())
            return pandas.date_range(start=lower_date, end=upper_date)

        tmp_df1 = df1.set_index("date")
        tmp_df2 = df2.set_index("date")

        row_list: list[pandas.Series] = []
        for dt in date_range():
            str_date = str(dt.date())
            if str_date in tmp_df1.index:
                row1 = tmp_df1.loc[str_date]
            else:
                row1 = None
            if str_date in tmp_df2.index:
                row2 = tmp_df2.loc[str_date]
            else:
                row2 = None

            sum_row = merge_row(str_date=str_date, columns=tmp_df1.columns, row1=row1, row2=row2)
            row_list.append(sum_row)

        sum_df = pandas.DataFrame(row_list)
        sum_df.index.name = "date"
        cls._add_velocity_columns(sum_df)
        return WholeProductivityPerCompletedDate(sum_df.reset_index())

    @staticmethod
    def _create_div_element() -> bokeh.models.Div:
        """
        HTMLページの先頭に付与するdiv要素を生成する。
        """
        return bokeh.models.Div(
            text="""<h4>用語</h4>
            <p>「X日のタスク数」とは、X日に初めて受入完了状態になったタスクの個数です。</p>
            """
        )

    def plot(self, output_file: Path):
        """
        全体の生産量や生産性をプロットする


        Args:
            df:

        Returns:

        """

        def add_velocity_columns(df: pandas.DataFrame):
            for denominator in ["input_data_count", "annotation_count"]:
                for category in [
                    "actual",
                    "monitored",
                    "monitored_annotation",
                    "monitored_inspection",
                    "monitored_acceptance",
                    "unmonitored",
                ]:
                    df[f"{category}_worktime_minute/{denominator}"] = (
                        df[f"{category}_worktime_hour"] * 60 / df[denominator]
                    )
                    df[f"{category}_worktime_minute/{denominator}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                        get_weekly_sum(df[f"{category}_worktime_hour"]) * 60 / get_weekly_sum(df[denominator])
                    )

            df[f"actual_worktime_hour/task_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(
                df["actual_worktime_hour"]
            ) / get_weekly_sum(df["task_count"])
            df[f"monitored_worktime_hour/task_count{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_sum(
                df["monitored_worktime_hour"]
            ) / get_weekly_sum(df["task_count"])

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
                plot_width=1200,
                plot_height=600,
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
                tooltip_columns=[
                    "date",
                    "task_count",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[hour]",
                secondary_y_axis_range=DataRange1d(
                    end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max())
                    * SECONDARY_Y_RANGE_RATIO
                ),
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
                tooltip_columns=[
                    "date",
                    "input_data_count",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[hour]",
                secondary_y_axis_range=DataRange1d(
                    end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max())
                    * SECONDARY_Y_RANGE_RATIO
                ),
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
                    y_axis_label="作業時間[hour]",
                    tooltip_columns=[
                        "date",
                        "actual_worktime_hour",
                        "monitored_worktime_hour",
                        "monitored_annotation_worktime_hour",
                        "monitored_inspection_worktime_hour",
                        "monitored_acceptance_worktime_hour",
                    ],
                ),
                "y_info_list": [{"column": f"{e[0]}_hour", "legend": f"{e[1]}"} for e in phase_prefix],
            },
            {
                "line_graph": create_line_graph(
                    title="日ごとの入力データあたり作業時間",
                    y_axis_label="入力データあたり作業時間[minute/input_data]",
                    tooltip_columns=[
                        "date",
                        "input_data_count",
                        "actual_worktime_hour",
                        "monitored_worktime_hour",
                        "monitored_annotation_worktime_hour",
                        "monitored_inspection_worktime_hour",
                        "monitored_acceptance_worktime_hour",
                        "actual_worktime_minute/input_data_count",
                        "monitored_worktime_minute/input_data_count",
                        "monitored_annotation_worktime_minute/input_data_count",
                        "monitored_inspection_worktime_minute/input_data_count",
                        "monitored_acceptance_worktime_minute/input_data_count",
                    ],
                ),
                "y_info_list": [
                    {"column": f"{e[0]}_minute/input_data_count", "legend": f"入力データあたり{e[1]}"} for e in phase_prefix
                ],
            },
            {
                "line_graph": create_line_graph(
                    title="日ごとのアノテーションあたり作業時間",
                    y_axis_label="アノテーションあたり作業時間[minute/annotation]",
                    tooltip_columns=[
                        "date",
                        "annotation_count",
                        "actual_worktime_hour",
                        "monitored_worktime_hour",
                        "monitored_annotation_worktime_hour",
                        "monitored_inspection_worktime_hour",
                        "monitored_acceptance_worktime_hour",
                        "actual_worktime_minute/annotation_count",
                        "monitored_worktime_minute/annotation_count",
                        "monitored_annotation_worktime_minute/annotation_count",
                        "monitored_inspection_worktime_minute/annotation_count",
                        "monitored_acceptance_worktime_minute/annotation_count",
                    ],
                ),
                "y_info_list": [
                    {"column": f"{e[0]}_minute/annotation_count", "legend": f"アノテーションあたり{e[1]}"} for e in phase_prefix
                ],
            },
        ]

        source = ColumnDataSource(data=df)

        for fig_info in fig_info_list:
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)
                line_graph: LineGraph = fig_info["line_graph"]  # type: ignore
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
        line_graph_list.extend([info["line_graph"] for info in fig_info_list])  # type: ignore

        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

        div_element = self._create_div_element()
        write_bokeh_graph(bokeh.layouts.column([div_element] + [e.figure for e in line_graph_list]), output_file)

    def plot_cumulatively(self, output_file: Path):
        """
        全体の生産量や作業時間の累積折れ線グラフを出力する
        """

        def create_line_graph(title: str, y_axis_label: str, tooltip_columns: list[str]) -> LineGraph:
            return LineGraph(
                plot_width=1200,
                plot_height=600,
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
                    "cumsum_task_count",
                    "cumsum_actual_worktime_hour",
                    "cumsum_monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[hour]",
                secondary_y_axis_range=DataRange1d(
                    end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max())
                    * SECONDARY_Y_RANGE_RATIO
                ),
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
                    "cumsum_input_data_count",
                    "cumsum_actual_worktime_hour",
                    "cumsum_monitored_worktime_hour",
                ],
            )
            line_graph.add_secondary_y_axis(
                "作業時間[hour]",
                secondary_y_axis_range=DataRange1d(
                    end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max())
                    * SECONDARY_Y_RANGE_RATIO
                ),
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
                y_axis_label="作業時間[hour]",
                tooltip_columns=[
                    "date",
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
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
        write_bokeh_graph(bokeh.layouts.column([div_element] + [e.figure for e in line_graph_list]), output_file)

    def to_csv(self, output_file: Path) -> None:
        """
        日毎の全体の生産量、生産性を出力する。

        """
        if not self._validate_df_for_output(output_file):
            return

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
            "unmonitored_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for suffix in ["", WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX]
            for numerator in ["actual_worktime_hour", "monitored_worktime_hour"]
            for denominator in ["task_count", "input_data_count", "annotation_count"]
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
            for denominator in ["input_data_count", "annotation_count"]
        ]

        columns = (
            [
                "date",
                "cumsum_task_count",
                "cumsum_input_data_count",
                "cumsum_actual_worktime_hour",
                "cumsum_monitored_worktime_hour",
            ]
            + production_columns
            + worktime_columns
            + velocity_columns
            + velocity_details_columns
            + ["working_user_count"]
        )

        print_csv(self.df[columns], output=str(output_file))


class WholeProductivityPerFirstAnnotationStartedDate:
    """教師付開始日ごとの全体の生産量と生産性に関する情報"""

    def __init__(self, df: pandas.DataFrame):
        self.df = df

    @classmethod
    def from_csv(cls, csv_file: Path) -> WholeProductivityPerFirstAnnotationStartedDate:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file))
        return cls(df)

    @classmethod
    def _add_velocity_columns(cls, df: pandas.DataFrame):
        """
        日毎の全体の生産量から、累計情報、生産性の列を追加する。
        """

        def add_velocity_column(df: pandas.DataFrame, numerator_column: str, denominator_column: str):
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]

            df[
                f"{numerator_column}/{denominator_column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"
            ] = get_weekly_moving_average(df[numerator_column]) / get_weekly_moving_average(df[denominator_column])

        # annofab 計測時間から算出したvelocityを追加
        add_velocity_column(df, numerator_column="worktime_hour", denominator_column="input_data_count")
        add_velocity_column(df, numerator_column="annotation_worktime_hour", denominator_column="input_data_count")
        add_velocity_column(df, numerator_column="inspection_worktime_hour", denominator_column="input_data_count")
        add_velocity_column(df, numerator_column="acceptance_worktime_hour", denominator_column="input_data_count")

        add_velocity_column(df, numerator_column="worktime_hour", denominator_column="annotation_count")
        add_velocity_column(df, numerator_column="annotation_worktime_hour", denominator_column="annotation_count")
        add_velocity_column(df, numerator_column="inspection_worktime_hour", denominator_column="annotation_count")
        add_velocity_column(df, numerator_column="acceptance_worktime_hour", denominator_column="annotation_count")

    @classmethod
    def from_df(cls, df_task: pandas.DataFrame) -> WholeProductivityPerFirstAnnotationStartedDate:
        df_sub_task = df_task[df_task["status"] == TaskStatus.COMPLETE.value][
            [
                "task_id",
                "first_annotation_started_datetime",
                "input_data_count",
                "annotation_count",
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        ].copy()
        df_sub_task["first_annotation_started_date"] = df_sub_task["first_annotation_started_datetime"].map(
            lambda e: datetime_to_date(e) if not pandas.isna(e) else None
        )

        value_columns = [
            "input_data_count",
            "annotation_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]
        df_agg_sub_task = df_sub_task.pivot_table(
            values=value_columns,
            index="first_annotation_started_date",
            aggfunc=numpy.sum,
        ).fillna(0)
        if len(df_agg_sub_task) > 0:
            df_agg_sub_task["task_count"] = df_sub_task.pivot_table(
                values=["task_id"], index="first_annotation_started_date", aggfunc="count"
            ).fillna(0)
        else:
            # 列だけ作る
            df_agg_sub_task = df_agg_sub_task.assign(**{key: 0 for key in value_columns}, task_count=0)

        # 日付の一覧を生成
        if len(df_agg_sub_task) > 0:
            df_date_base = pandas.DataFrame(
                index=[
                    e.strftime("%Y-%m-%d")
                    for e in pandas.date_range(start=df_agg_sub_task.index.min(), end=df_agg_sub_task.index.max())
                ]
            )
        else:
            df_date_base = pandas.DataFrame()

        df_date = df_date_base.join(df_agg_sub_task).fillna(0)

        df_date["first_annotation_started_date"] = df_date.index

        # 生産性情報などの列を追加する
        cls._add_velocity_columns(df_date)
        return cls(df_date)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    def to_csv(self, output_file: Path) -> pandas.DataFrame:
        if not self._validate_df_for_output(output_file):
            return

        basic_columns = [
            "first_annotation_started_date",
            "task_count",
            "input_data_count",
            "annotation_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for suffix in ["", WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX]
            for denominator in ["input_data_count", "annotation_count"]
            for numerator in [
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        ]

        columns = basic_columns + velocity_columns

        print_csv(self.df[columns], str(output_file))

    @classmethod
    def merge(
        cls, obj1: WholeProductivityPerFirstAnnotationStartedDate, obj2: WholeProductivityPerFirstAnnotationStartedDate
    ) -> WholeProductivityPerFirstAnnotationStartedDate:
        def merge_row(
            str_date: str, columns: pandas.Index, row1: Optional[pandas.Series], row2: Optional[pandas.Series]
        ) -> pandas.Series:
            if row1 is not None and row2 is not None:
                sum_row = row1.fillna(0) + row2.fillna(0)
            elif row1 is not None and row2 is None:
                sum_row = row1.fillna(0)
            elif row1 is None and row2 is not None:
                sum_row = row2.fillna(0)
            else:
                sum_row = pandas.Series(index=columns)

            sum_row.name = str_date
            return sum_row

        def date_range():
            lower_date = min(df1["first_annotation_started_date"].min(), df2["first_annotation_started_date"].min())
            upper_date = max(df1["first_annotation_started_date"].max(), df2["first_annotation_started_date"].max())
            return pandas.date_range(start=lower_date, end=upper_date)

        df1 = obj1.df
        df2 = obj2.df
        tmp_df1 = df1.set_index("first_annotation_started_date")
        tmp_df2 = df2.set_index("first_annotation_started_date")

        row_list: list[pandas.Series] = []
        for dt in date_range():
            str_date = str(dt.date())
            if str_date in tmp_df1.index:
                row1 = tmp_df1.loc[str_date]
            else:
                row1 = None
            if str_date in tmp_df2.index:
                row2 = tmp_df2.loc[str_date]
            else:
                row2 = None

            sum_row = merge_row(str_date=str_date, columns=tmp_df1.columns, row1=row1, row2=row2)
            row_list.append(sum_row)

        sum_df = pandas.DataFrame(row_list)
        sum_df.index.name = "first_annotation_started_date"
        sum_df.reset_index(inplace=True)
        cls._add_velocity_columns(sum_df)
        return cls(sum_df)

    def plot(self, output_file: Path):
        """
        全体の生産量や生産性をプロットする
        """

        def add_velocity_and_weekly_moving_average_columns(df):
            for column in [
                "task_count",
                "input_data_count",
                "worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]:
                df[f"{column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_moving_average(df[column])

            for denominator in ["input_data_count", "annotation_count"]:
                for numerator in ["worktime", "annotation_worktime", "inspection_worktime", "acceptance_worktime"]:
                    df[f"{numerator}_minute/{denominator}"] = df[f"{numerator}_hour"] * 60 / df[denominator]
                    df[f"{numerator}_minute/{denominator}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = (
                        get_weekly_sum(df[f"{numerator}_hour"]) * 60 / get_weekly_sum(df[denominator])
                    )

        def create_div_element() -> bokeh.models.Div:
            """
            HTMLページの先頭に付与するdiv要素を生成する。
            """
            return bokeh.models.Div(
                text="""<h4>注意</h4>
                <p>「X日の作業時間」とは、「X日に教師付開始したタスクにかけた作業時間」です。
                「X日に作業した時間」ではありません。
                </p>
                """
            )

        def create_line_graph(title: str, y_axis_label: str, tooltip_columns: list[str]) -> LineGraph:
            return LineGraph(
                plot_width=1200,
                plot_height=600,
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
                "作業時間[hour]",
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

            line_graph.add_secondary_y_axis("作業時間[hour]")

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

        df = self.df.copy()
        df["dt_first_annotation_started_date"] = df["first_annotation_started_date"].map(lambda e: parse(e).date())
        add_velocity_and_weekly_moving_average_columns(df)

        logger.debug(f"{output_file} を出力します。")

        fig_info_list = [
            {
                "y_info_list": [
                    {"column": "worktime_hour", "legend": "計測作業時間"},
                    {"column": "annotation_worktime_hour", "legend": "計測作業時間(教師付)"},
                    {"column": "inspection_worktime_hour", "legend": "計測作業時間(検査)"},
                    {"column": "acceptance_worktime_hour", "legend": "計測作業時間(受入)"},
                ],
            },
            {
                "y_info_list": [
                    {"column": "worktime_minute/input_data_count", "legend": "入力データあたり計測作業時間"},
                    {"column": "annotation_worktime_minute/input_data_count", "legend": "入力データあたり計測作業時間(教師付)"},
                    {"column": "inspection_worktime_minute/input_data_count", "legend": "入力データあたり計測作業時間(検査)"},
                    {"column": "acceptance_worktime_minute/input_data_count", "legend": "入力データあたり計測作業時間(受入)"},
                ],
            },
            {
                "y_info_list": [
                    {"column": "worktime_minute/annotation_count", "legend": "アノテーションあたり計測作業時間"},
                    {"column": "annotation_worktime_minute/annotation_count", "legend": "アノテーションあたり計測作業時間(教師付)"},
                    {"column": "inspection_worktime_minute/annotation_count", "legend": "アノテーションあたり計測作業時間(検査)"},
                    {"column": "acceptance_worktime_minute/annotation_count", "legend": "アノテーションあたり計測作業時間(受入)"},
                ],
            },
        ]

        line_graph_list = [
            create_line_graph(
                title="教師付開始日ごとの計測作業時間",
                y_axis_label="作業時間[hour]",
                tooltip_columns=[
                    "first_annotation_started_date",
                    "worktime_hour",
                    "annotation_worktime_hour",
                    "inspection_worktime_hour",
                    "acceptance_worktime_hour",
                ],
            ),
            create_line_graph(
                title="教師付開始日ごとの入力データあたり計測作業時間",
                y_axis_label="入力データあたり作業時間[minute/input_data]",
                tooltip_columns=[
                    "first_annotation_started_date",
                    "input_data_count",
                    "worktime_hour",
                    "annotation_worktime_hour",
                    "inspection_worktime_hour",
                    "acceptance_worktime_hour",
                    "worktime_minute/input_data_count",
                    "annotation_worktime_minute/input_data_count",
                    "inspection_worktime_minute/input_data_count",
                    "acceptance_worktime_minute/input_data_count",
                ],
            ),
            create_line_graph(
                title="教師付開始日ごとのアノテーションあたり計測作業時間",
                y_axis_label="アノテーションあたり作業時間[minute/annotation]",
                tooltip_columns=[
                    "first_annotation_started_date",
                    "annotation_count",
                    "worktime_hour",
                    "annotation_worktime_hour",
                    "inspection_worktime_hour",
                    "acceptance_worktime_hour",
                    "worktime_minute/annotation_count",
                    "annotation_worktime_minute/annotation_count",
                    "inspection_worktime_minute/annotation_count",
                    "acceptance_worktime_minute/annotation_count",
                ],
            ),
        ]

        source = ColumnDataSource(data=df)

        for line_graph, fig_info in zip(line_graph_list, fig_info_list):
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)

                _plot_and_moving_average(
                    line_graph,
                    x_column="dt_first_annotation_started_date",
                    y_column=y_info["column"],
                    legend_name=y_info["legend"],
                    source=source,
                    color=color,
                )

        line_graph_list = [create_task_graph(), create_input_data_graph()] + line_graph_list

        for line_graph in line_graph_list:
            line_graph.process_after_adding_glyphs()

        write_bokeh_graph(
            bokeh.layouts.column([create_div_element()] + [e.figure for e in line_graph_list]), output_file
        )
