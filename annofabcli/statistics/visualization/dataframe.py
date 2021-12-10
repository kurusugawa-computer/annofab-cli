from __future__ import annotations
import logging
from pathlib import Path

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
from annofabapi.models import TaskStatus
from bokeh.models import DataRange1d, LinearAxis
from bokeh.plotting import ColumnDataSource, figure
from dateutil.parser import parse
from annofabcli.common.utils import print_csv
from annofabcli.common.utils import datetime_to_date
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


class WholeProductivityPerFirstAnnotationDate:



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
    def to_csv(cls, df: pandas.DataFrame, output_file:Path) -> pandas.DataFrame:
        if len(df) == 0:
            logger.info("データ件数が0件のため出力しません。")
            return

        columns = [
            "first_annotation_started_date",
            "task_count",
            "input_data_count",

            "annotation_count",
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
                y_range_name: DataRange1d(
                    end=df["worktime_hour"].max() * (1 + y_overlimit)
                )
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
            logger.info("データが0件のため出力しない")
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
                    fig=fig, x_column_name="dt_first_annotation_started_date", y_column_name=y_info["column"], legend_name=y_info["legend"], source=source, color=color
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

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)

        bokeh.plotting.save(bokeh.layouts.column([create_div_element()] + fig_list))

