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
from bokeh.models import DataRange1d, LinearAxis
from bokeh.plotting import ColumnDataSource, figure
from dateutil.parser import parse

from annofabcli.common.utils import datetime_to_date, print_csv
from annofabcli.statistics.linegraph import (
    add_legend_to_figure,
    create_hover_tool,
    get_color_from_small_palette,
    plot_line_and_circle,
    plot_moving_average,
)

logger = logging.getLogger(__name__)


WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX = "__lastweek"
"""1週間移動平均を表す列名のsuffix"""


def get_weekly_moving_average(df: pandas.DataFrame, column: str) -> pandas.Series:
    """1週間移動平均をプロットするために、1週間移動平均用のpandas.Seriesを取得する。"""
    MOVING_WINDOW_DAYS = 7
    MIN_WINDOW_DAYS = 2
    tmp = column.split("/")
    if len(tmp) == 2:
        numerator_column, denominator_column = tmp[0], tmp[1]
        return (
            df[numerator_column].rolling(MOVING_WINDOW_DAYS, min_periods=MIN_WINDOW_DAYS).sum()
            / df[denominator_column].rolling(MOVING_WINDOW_DAYS, min_periods=MIN_WINDOW_DAYS).sum()
        )
    else:
        return df[column].rolling(MOVING_WINDOW_DAYS, min_periods=MIN_WINDOW_DAYS).mean()


class WholeProductivityPerCompletedDate:
    """受入完了日ごとの全体の生産量と生産性に関する情報"""

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
    def create(cls, df_task: pandas.DataFrame, df_labor: pandas.DataFrame) -> pandas.DataFrame:
        """
        受入完了日毎の全体の生産量、生産性を算出する。
        """
        df_sub_task = df_task[
            [
                "task_id",
                "task_completed_datetime",
                "input_data_count",
                "annotation_count",
                "sum_worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
            ]
        ].copy()
        df_sub_task["task_completed_date"] = df_sub_task["task_completed_datetime"].map(
            lambda e: datetime_to_date(e) if not pandas.isna(e) else None
        )

        # タスク完了日を軸にして集計する
        value_columns = [
            "input_data_count",
            "annotation_count",
            "sum_worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
        ]
        df_agg_sub_task = df_sub_task.pivot_table(
            values=value_columns,
            index="task_completed_date",
            aggfunc=numpy.sum,
        ).fillna(0)
        if len(df_agg_sub_task) > 0:
            df_agg_sub_task["task_count"] = df_sub_task.pivot_table(
                values=["task_id"], index="task_completed_date", aggfunc="count"
            ).fillna(0)
        else:
            # 列だけ作る
            df_agg_sub_task = df_agg_sub_task.assign(**{key: 0 for key in value_columns}, task_count=0)

        if len(df_labor) > 0:
            df_labor2 = df_labor[df_labor["actual_worktime_hour"] > 0]
            df_agg_labor = df_labor2.pivot_table(
                values=["actual_worktime_hour"], index="date", aggfunc=numpy.sum
            ).fillna(0)

            if "actual_worktime_hour" not in df_agg_labor.columns:
                # len(df_labor2)==0 のときの状況
                df_agg_labor["actual_worktime_hour"] = 0
            df_tmp = df_labor2.pivot_table(values=["user_id"], index="date", aggfunc="count").fillna(0)

            if len(df_tmp) > 0:
                df_agg_labor["working_user_count"] = df_tmp
            else:
                df_agg_labor["working_user_count"] = 0

        else:
            df_agg_labor = pandas.DataFrame(columns=["actual_worktime_hour", "working_user_count"])

        # 日付の一覧を生成
        df_date_base = cls._create_df_date(df_agg_sub_task.index, df_agg_labor.index)
        df_date = df_date_base.join(df_agg_sub_task).join(df_agg_labor).fillna(0)
        df_date.rename(
            columns={
                "sum_worktime_hour": "monitored_worktime_hour",
                "annotation_worktime_hour": "monitored_annotation_worktime_hour",
                "inspection_worktime_hour": "monitored_inspection_worktime_hour",
                "acceptance_worktime_hour": "monitored_acceptance_worktime_hour",
                "actual_worktime_hour": "actual_worktime_hour",
                "user_id": "working_user_count",
            },
            inplace=True,
        )
        df_date["date"] = df_date.index

        cls._add_velocity_columns(df_date)
        return df_date

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
            MOVING_WINDOW_SIZE = 7
            MIN_WINDOW_SIZE = 2
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]
            df[f"{numerator_column}/{denominator_column}__lastweek"] = (
                df[numerator_column].rolling(MOVING_WINDOW_SIZE, min_periods=MIN_WINDOW_SIZE).sum()
                / df[denominator_column].rolling(MOVING_WINDOW_SIZE, min_periods=MIN_WINDOW_SIZE).sum()
            )

        # 累計情報を追加
        add_cumsum_column(df, column="task_count")
        add_cumsum_column(df, column="input_data_count")
        add_cumsum_column(df, column="actual_worktime_hour")

        # annofab 計測時間から算出したvelocityを追加
        add_velocity_column(df, numerator_column="monitored_worktime_hour", denominator_column="task_count")
        add_velocity_column(df, numerator_column="monitored_worktime_hour", denominator_column="input_data_count")
        add_velocity_column(df, numerator_column="monitored_worktime_hour", denominator_column="annotation_count")

        # 実績作業時間から算出したvelocityを追加
        add_velocity_column(df, numerator_column="actual_worktime_hour", denominator_column="task_count")
        add_velocity_column(df, numerator_column="actual_worktime_hour", denominator_column="input_data_count")
        add_velocity_column(df, numerator_column="actual_worktime_hour", denominator_column="annotation_count")

        # CSVには"INF"という文字を出力したくないので、"INF"をNaNに置換する
        df.replace([numpy.inf, -numpy.inf], numpy.nan, inplace=True)
        return df

    @classmethod
    def merge(cls, df1: pandas.DataFrame, df2: pandas.DataFrame) -> pandas.DataFrame:
        """
        日毎の全体の生産量、生産性が格納されたDataFrameを結合する。

        Args:
            df1:
            df2:

        Returns:
            マージ済のユーザごとの生産性・品質情報
        """

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
        return sum_df.reset_index()

    @classmethod
    def plot(cls, df: pandas.DataFrame, output_file: Path):
        """
        全体の生産量や生産性をプロットする


        Args:
            df:

        Returns:

        """

        def create_figure(title: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=600,
                title=title,
                x_axis_label="日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
            )

        def plot_and_moving_average(fig, y_column_name: str, legend_name: str, source, color, **kwargs):
            x_column_name = "dt_date"

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name=y_column_name,
                source=source,
                color=color,
                legend_label=legend_name,
                **kwargs,
            )

            # 移動平均をプロット
            plot_moving_average(
                fig,
                x_column_name=x_column_name,
                y_column_name=f"{y_column_name}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
                source=source,
                color=color,
                legend_label=f"{legend_name}の1週間移動平均",
                **kwargs,
            )

        def create_task_figure():
            y_range_name = "worktime_axis"
            fig_task = create_figure(title="日ごとのタスク数と作業時間", y_axis_label="タスク数")
            fig_task.add_layout(
                LinearAxis(
                    y_range_name=y_range_name,
                    axis_label="作業時間[hour]",
                ),
                "right",
            )
            y_overlimit = 0.05
            fig_task.extra_y_ranges = {
                y_range_name: DataRange1d(
                    end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max()) * (1 + y_overlimit)
                )
            }
            plot_and_moving_average(
                fig=fig_task,
                y_column_name="task_count",
                legend_name="タスク数",
                source=source,
                color=get_color_from_small_palette(0),
            )
            plot_and_moving_average(
                fig=fig_task,
                y_column_name="actual_worktime_hour",
                legend_name="実績作業時間",
                source=source,
                color=get_color_from_small_palette(1),
                y_range_name=y_range_name,
            )
            plot_and_moving_average(
                fig=fig_task,
                y_column_name="monitored_worktime_hour",
                legend_name="計測作業時間",
                source=source,
                color=get_color_from_small_palette(2),
                y_range_name=y_range_name,
            )
            return fig_task

        def create_input_data_figure():
            y_range_name = "worktime_axis"
            fig_input_data = create_figure(title="日ごとの入力データ数と作業時間", y_axis_label="入力データ数")
            fig_input_data.add_layout(
                LinearAxis(
                    y_range_name=y_range_name,
                    axis_label="作業時間[hour]",
                ),
                "right",
            )
            y_overlimit = 0.05
            fig_input_data.extra_y_ranges = {
                y_range_name: DataRange1d(
                    end=max(df["actual_worktime_hour"].max(), df["monitored_worktime_hour"].max()) * (1 + y_overlimit)
                )
            }
            plot_and_moving_average(
                fig=fig_input_data,
                y_column_name="input_data_count",
                legend_name="入力データ数",
                source=source,
                color=get_color_from_small_palette(0),
            )
            plot_and_moving_average(
                fig=fig_input_data,
                y_column_name="actual_worktime_hour",
                legend_name="実績作業時間",
                source=source,
                color=get_color_from_small_palette(1),
                y_range_name=y_range_name,
            )
            plot_and_moving_average(
                fig=fig_input_data,
                y_column_name="monitored_worktime_hour",
                legend_name="計測作業時間",
                source=source,
                color=get_color_from_small_palette(2),
                y_range_name=y_range_name,
            )
            return fig_input_data

        if len(df) == 0:
            logger.warning(f"データ件数が0件のため {output_file} は出力しません。")
            return

        df["dt_date"] = df["date"].map(lambda e: parse(e).date())

        logger.debug(f"{output_file} を出力します。")

        fig_list = [
            create_figure(title="日ごとの作業時間", y_axis_label="作業時間[hour]"),
            create_figure(title="日ごとのタスクあたり作業時間", y_axis_label="タスクあたり作業時間[hour/task]"),
            create_figure(title="日ごとの入力データあたり作業時間", y_axis_label="入力データあたり作業時間[hour/input_data]"),
            create_figure(title="日ごとのアノテーションあたり作業時間", y_axis_label="アノテーションあたり作業時間[hour/annotation]"),
        ]

        fig_info_list = [
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "actual_worktime_hour", "legend": "実績作業時間"},
                    {"column": "monitored_worktime_hour", "legend": "計測作業時間"},
                ],
            },
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "actual_worktime_hour/task_count", "legend": "タスクあたり実績作業時間"},
                    {"column": "monitored_worktime_hour/task_count", "legend": "タスクあたり計測作業時間"},
                ],
            },
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "actual_worktime_hour/input_data_count", "legend": "入力データあたり実績作業時間"},
                    {"column": "monitored_worktime_hour/input_data_count", "legend": "入力データあたり計測作業時間"},
                ],
            },
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "actual_worktime_hour/annotation_count", "legend": "アノテーションあたり実績作業時間"},
                    {"column": "monitored_worktime_hour/annotation_count", "legend": "アノテーションあたり計測作業時間"},
                ],
            },
        ]

        MOVING_WINDOW_SIZE = 7
        for column in ["task_count", "input_data_count", "actual_worktime_hour", "monitored_worktime_hour"]:
            df[f"{column}__lastweek"] = df[column].rolling(MOVING_WINDOW_SIZE).mean()

        source = ColumnDataSource(data=df)

        for fig, fig_info in zip(fig_list, fig_info_list):
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)

                plot_and_moving_average(
                    fig=fig, y_column_name=y_info["column"], legend_name=y_info["legend"], source=source, color=color
                )

        tooltip_item = [
            "date",
            "task_count",
            "input_data_count",
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "cumsum_task_count",
            "cumsum_input_data_count",
            "cumsum_actual_worktime_hour",
            "actual_worktime_hour/task_count",
            "actual_worktime_hour/input_data_count",
            "actual_worktime_hour/annotation_count",
            "monitored_worktime_hour/task_count",
            "monitored_worktime_hour/input_data_count",
            "monitored_worktime_hour/annotation_count",
        ]
        hover_tool = create_hover_tool(tooltip_item)

        fig_list.insert(0, create_task_figure())
        fig_list.insert(1, create_input_data_figure())

        for fig in fig_list:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh.layouts.column(fig_list))

    @classmethod
    def plot_cumulatively(cls, df: pandas.DataFrame, output_file: Path):
        """
        全体の生産量や作業時間の累積折れ線グラフを出力する
        """

        def create_figure(title: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=600,
                title=title,
                x_axis_label="日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
            )

        def create_task_figure():
            y_range_name = "worktime_axis"
            fig = create_figure(title="日ごとの累積タスク数と累積作業時間", y_axis_label="タスク数")
            fig.add_layout(
                LinearAxis(
                    y_range_name=y_range_name,
                    axis_label="作業時間[hour]",
                ),
                "right",
            )
            y_overlimit = 0.05
            fig.extra_y_ranges = {
                y_range_name: DataRange1d(
                    end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max())
                    * (1 + y_overlimit)
                )
            }

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_task_count",
                source=source,
                color=get_color_from_small_palette(0),
                legend_label="タスク数",
            )

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_actual_worktime_hour",
                source=source,
                color=get_color_from_small_palette(1),
                legend_label="実績作業時間",
                y_range_name=y_range_name,
            )
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_monitored_worktime_hour",
                source=source,
                color=get_color_from_small_palette(2),
                legend_label="計測作業時間",
                y_range_name=y_range_name,
            )

            return fig

        def create_input_data_figure():
            y_range_name = "worktime_axis"
            fig = create_figure(title="日ごとの累積入力データ数と累積作業時間", y_axis_label="入力データ数")
            fig.add_layout(
                LinearAxis(
                    y_range_name=y_range_name,
                    axis_label="作業時間[hour]",
                ),
                "right",
            )
            y_overlimit = 0.05
            fig.extra_y_ranges = {
                y_range_name: DataRange1d(
                    end=max(df["cumsum_actual_worktime_hour"].max(), df["cumsum_monitored_worktime_hour"].max())
                    * (1 + y_overlimit)
                )
            }

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_input_data_count",
                source=source,
                color=get_color_from_small_palette(0),
                legend_label="入力データ数",
            )

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_actual_worktime_hour",
                source=source,
                color=get_color_from_small_palette(1),
                legend_label="実績作業時間",
                y_range_name=y_range_name,
            )

            # 値をプロット
            plot_line_and_circle(
                fig,
                x_column_name=x_column_name,
                y_column_name="cumsum_monitored_worktime_hour",
                source=source,
                color=get_color_from_small_palette(2),
                legend_label="計測作業時間",
                y_range_name=y_range_name,
            )

            return fig

        if len(df) == 0:
            logger.warning(f"データ件数が0件のため {output_file} は出力しません。")
            return

        df["dt_date"] = df["date"].map(lambda e: parse(e).date())
        df["cumsum_monitored_worktime_hour"] = df["monitored_worktime_hour"].cumsum()

        logger.debug(f"{output_file} を出力します。")

        fig_list = [
            create_figure(title="日ごとの累積作業時間", y_axis_label="作業時間[hour]"),
        ]

        fig_info_list = [
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "cumsum_actual_worktime_hour", "legend": "実績作業時間"},
                    {"column": "cumsum_monitored_worktime_hour", "legend": "計測作業時間"},
                ],
            },
        ]

        source = ColumnDataSource(data=df)

        for fig, fig_info in zip(fig_list, fig_info_list):
            x_column_name = "dt_date"
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)

                # 値をプロット
                plot_line_and_circle(
                    fig,
                    x_column_name=x_column_name,
                    y_column_name=y_info["column"],
                    source=source,
                    color=color,
                    legend_label=y_info["legend"],
                )

        tooltip_item = [
            "date",
            "task_count",
            "input_data_count",
            "actual_worktime_hour",
            "monitored_worktime_hour",
            "cumsum_task_count",
            "cumsum_input_data_count",
            "cumsum_actual_worktime_hour",
            "cumsum_monitored_worktime_hour",
        ]
        hover_tool = create_hover_tool(tooltip_item)

        fig_list.insert(0, create_task_figure())
        fig_list.insert(1, create_input_data_figure())

        for fig in fig_list:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh.layouts.column(fig_list))

    @classmethod
    def to_csv(cls, df: pandas.DataFrame, output_file: Path) -> None:
        """
        日毎の全体の生産量、生産性を出力する。

        """
        if len(df) == 0:
            logger.warning(f"データ件数が0件のため {output_file} は出力しません。")
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
        ]

        velocity_columns = [
            f"{numerator}/{denominator}{suffix}"
            for numerator in ["actual_worktime_hour", "monitored_worktime_hour"]
            for denominator in ["task_count", "input_data_count", "annotation_count"]
            for suffix in ["", "__lastweek"]
        ]

        columns = (
            ["date", "cumsum_task_count", "cumsum_input_data_count", "cumsum_actual_worktime_hour"]
            + production_columns
            + worktime_columns
            + velocity_columns
            + ["working_user_count"]
        )

        print_csv(df[columns], output=str(output_file))


class WholeProductivityPerFirstAnnotationStartedDate:
    """教師付開始日ごとの全体の生産量と生産性に関する情報"""

    @classmethod
    def create(cls, df_task: pandas.DataFrame) -> pandas.DataFrame:
        """
        教師付開始日ごとに、日毎の全体の生産量と生産性が格納されたDataFrameを生成する。
        """

        df_sub_task = df_task[df_task["status"] == TaskStatus.COMPLETE.value][
            [
                "task_id",
                "first_annotation_started_datetime",
                "input_data_count",
                "annotation_count",
                "sum_worktime_hour",
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
            "sum_worktime_hour",
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
        df_date_base = pandas.DataFrame(
            index=[
                e.strftime("%Y-%m-%d")
                for e in pandas.date_range(start=df_agg_sub_task.index.min(), end=df_agg_sub_task.index.max())
            ]
        )
        df_date = df_date_base.join(df_agg_sub_task).fillna(0)

        df_date.rename(
            columns={
                "sum_worktime_hour": "worktime_hour",
            },
            inplace=True,
        )
        df_date["first_annotation_started_date"] = df_date.index

        # 生産性情報などの列を追加する
        cls._add_velocity_columns(df_date)
        return df_date

    @classmethod
    def to_csv(cls, df: pandas.DataFrame, output_file: Path) -> pandas.DataFrame:
        if len(df) == 0:
            logger.warning(f"データ件数が0件のため {output_file} は出力しません。")
            return

        columns = [
            "first_annotation_started_date",
            "task_count",
            "input_data_count",
            "annotation_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "worktime_hour/input_data_count",
            "annotation_worktime_hour/input_data_count",
            "inspection_worktime_hour/input_data_count",
            "acceptance_worktime_hour/input_data_count",
            "worktime_hour/annotation_count",
            "annotation_worktime_hour/annotation_count",
            "inspection_worktime_hour/annotation_count",
            "acceptance_worktime_hour/annotation_count",
        ]

        # # CSVには"INF"という文字を出力したくないので、"INF"をNaNに置換する
        # df.replace([numpy.inf, -numpy.inf], numpy.nan, inplace=True)
        print_csv(df[columns], str(output_file))

    @classmethod
    def _add_velocity_columns(cls, df: pandas.DataFrame):
        """
        日毎の全体の生産量から、累計情報、生産性の列を追加する。
        """

        def add_velocity_column(df: pandas.DataFrame, numerator_column: str, denominator_column: str):
            """速度情報の列を追加"""
            MOVING_WINDOW_SIZE = 7
            MIN_WINDOW_SIZE = 2
            df[f"{numerator_column}/{denominator_column}"] = df[numerator_column] / df[denominator_column]
            df[f"{numerator_column}/{denominator_column}__lastweek"] = (
                df[numerator_column].rolling(MOVING_WINDOW_SIZE, min_periods=MIN_WINDOW_SIZE).sum()
                / df[denominator_column].rolling(MOVING_WINDOW_SIZE, min_periods=MIN_WINDOW_SIZE).sum()
            )

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
    def merge(cls, df1: pandas.DataFrame, df2: pandas.DataFrame) -> pandas.DataFrame:
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
        cls._add_velocity_columns(sum_df)
        return sum_df.reset_index()

    @classmethod
    def _plot_and_moving_average(
        cls,
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_name: str,
        color,
        **kwargs,
    ):
        """

        Args:
            fig ([type]): [description]
            y_column_name (str): [description]
            legend_name (str): [description]
            source ([type]): [description]
            color ([type]): [description]
        """

        # 値をプロット
        plot_line_and_circle(
            fig,
            x_column_name=x_column_name,
            y_column_name=y_column_name,
            source=source,
            color=color,
            legend_label=legend_name,
            **kwargs,
        )

        # 移動平均をプロット
        plot_moving_average(
            fig,
            x_column_name=x_column_name,
            y_column_name=f"{y_column_name}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}",
            source=source,
            color=color,
            legend_label=f"{legend_name}の1週間移動平均",
            **kwargs,
        )

    @classmethod
    def plot(cls, df: pandas.DataFrame, output_file: Path):
        """
        全体の生産量や生産性をプロットする


        Args:
            df:

        Returns:

        """

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

        def create_figure(title: str, y_axis_label: str) -> bokeh.plotting.Figure:
            return figure(
                plot_width=1200,
                plot_height=600,
                title=title,
                x_axis_label="教師開始日",
                x_axis_type="datetime",
                y_axis_label=y_axis_label,
            )

        def create_input_data_figure():
            y_range_name = "worktime_axis"
            fig_input_data = create_figure(title="日ごとの入力データ数と作業時間", y_axis_label="入力データ数")
            fig_input_data.add_layout(
                LinearAxis(
                    y_range_name=y_range_name,
                    axis_label="作業時間[hour]",
                ),
                "right",
            )
            y_overlimit = 0.05
            fig_input_data.extra_y_ranges = {
                y_range_name: DataRange1d(end=df["worktime_hour"].max() * (1 + y_overlimit))
            }
            cls._plot_and_moving_average(
                fig=fig_input_data,
                x_column_name="dt_first_annotation_started_date",
                y_column_name="input_data_count",
                legend_name="入力データ数",
                source=source,
                color=get_color_from_small_palette(0),
            )
            cls._plot_and_moving_average(
                fig=fig_input_data,
                x_column_name="dt_first_annotation_started_date",
                y_column_name="worktime_hour",
                legend_name="作業時間",
                source=source,
                color=get_color_from_small_palette(1),
                y_range_name=y_range_name,
            )
            return fig_input_data

        if len(df) == 0:
            logger.warning(f"データ件数が0件のため {output_file} は出力しません。")
            return

        df["dt_first_annotation_started_date"] = df["first_annotation_started_date"].map(lambda e: parse(e).date())

        logger.debug(f"{output_file} を出力します。")

        fig_list = [
            create_figure(title="教師付開始日ごとの作業時間", y_axis_label="作業時間[hour]"),
            create_figure(title="教師付開始日ごとの入力データあたり作業時間", y_axis_label="入力データあたり作業時間[hour/input_data]"),
            create_figure(title="教師付開始日ごとのアノテーションあたり作業時間", y_axis_label="アノテーションあたり作業時間[hour/annotation]"),
        ]

        fig_info_list = [
            {
                "x": "dt_first_annotation_started_date",
                "y_info_list": [
                    {"column": "worktime_hour", "legend": "作業時間(合計)"},
                    {"column": "annotation_worktime_hour", "legend": "作業時間(教師付)"},
                    {"column": "inspection_worktime_hour", "legend": "作業時間(検査)"},
                    {"column": "acceptance_worktime_hour", "legend": "作業時間(受入)"},
                ],
            },
            {
                "x": "dt_first_annotation_started_date",
                "y_info_list": [
                    {"column": "worktime_hour/input_data_count", "legend": "入力データあたり作業時間(合計)"},
                    {"column": "annotation_worktime_hour/input_data_count", "legend": "入力データあたり作業時間(教師付)"},
                    {"column": "inspection_worktime_hour/input_data_count", "legend": "入力データあたり作業時間(検査)"},
                    {"column": "acceptance_worktime_hour/input_data_count", "legend": "入力データあたり作業時間(受入)"},
                ],
            },
            {
                "x": "dt_date",
                "y_info_list": [
                    {"column": "worktime_hour/annotation_count", "legend": "入力データあたり作業時間(合計)"},
                    {"column": "annotation_worktime_hour/annotation_count", "legend": "入力データあたり作業時間(教師付)"},
                    {"column": "inspection_worktime_hour/annotation_count", "legend": "入力データあたり作業時間(検査)"},
                    {"column": "acceptance_worktime_hour/annotation_count", "legend": "入力データあたり作業時間(受入)"},
                ],
            },
        ]

        # 1週間移動平均用の列を追加する
        for column in [
            "input_data_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "worktime_hour/input_data_count",
            "annotation_worktime_hour/input_data_count",
            "inspection_worktime_hour/input_data_count",
            "acceptance_worktime_hour/input_data_count",
            "worktime_hour/annotation_count",
            "annotation_worktime_hour/annotation_count",
            "inspection_worktime_hour/annotation_count",
            "acceptance_worktime_hour/annotation_count",
        ]:
            df[f"{column}{WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX}"] = get_weekly_moving_average(df, column)

        source = ColumnDataSource(data=df)

        for fig, fig_info in zip(fig_list, fig_info_list):
            y_info_list: list[dict[str, str]] = fig_info["y_info_list"]  # type: ignore
            for index, y_info in enumerate(y_info_list):
                color = get_color_from_small_palette(index)

                cls._plot_and_moving_average(
                    fig=fig,
                    x_column_name="dt_first_annotation_started_date",
                    y_column_name=y_info["column"],
                    legend_name=y_info["legend"],
                    source=source,
                    color=color,
                )

        tooltip_item = [
            "first_annotation_started_date",
            "task_count",
            "input_data_count",
            "annotation_count",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "worktime_hour/input_data_count",
            "annotation_worktime_hour/input_data_count",
            "inspection_worktime_hour/input_data_count",
            "acceptance_worktime_hour/input_data_count",
            "worktime_hour/annotation_count",
            "annotation_worktime_hour/annotation_count",
            "inspection_worktime_hour/annotation_count",
            "acceptance_worktime_hour/annotation_count",
        ]
        hover_tool = create_hover_tool(tooltip_item)

        fig_list.insert(0, create_input_data_figure())

        for fig in fig_list:
            fig.add_tools(hover_tool)
            add_legend_to_figure(fig)

        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)

        bokeh.plotting.save(bokeh.layouts.column([create_div_element()] + fig_list))