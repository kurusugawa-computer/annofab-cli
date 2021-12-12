# pylint: disable=too-many-lines
import logging
from enum import Enum
from pathlib import Path
from typing import List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import dateutil
import dateutil.parser
import pandas
from bokeh.core.properties import Color
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)

MAX_USER_COUNT_FOR_LINE_GRAPH = 20
"""折れ線グラフにプロットできる最大のユーザ数"""


WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX = "__lastweek"
"""1週間移動平均を表す列名のsuffix"""


def write_bokeh_graph(bokeh_obj, output_file: Path):
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)


def get_weekly_moving_average(series: pandas.Series) -> pandas.Series:
    """1週間移動平均をプロットするために、1週間移動平均用のpandas.Seriesを取得する。"""
    MOVING_WINDOW_DAYS = 7
    MIN_WINDOW_DAYS = 2
    return series.rolling(MOVING_WINDOW_DAYS, min_periods=MIN_WINDOW_DAYS).sum()


def get_color_from_palette(index: int) -> Color:
    my_palette = bokeh.palettes.Category20[20]
    return my_palette[index % len(my_palette)]


def get_color_from_small_palette(index: int) -> Color:
    my_palette = bokeh.palettes.Category10[10]
    return my_palette[index % len(my_palette)]


def add_legend_to_figure(fig: bokeh.plotting.Figure) -> None:
    """
    グラフに凡例を設定する。
    """
    fig.legend.location = "top_left"
    fig.legend.click_policy = "mute"
    if len(fig.legend) > 0:
        legend = fig.legend[0]
        fig.add_layout(legend, "left")


def plot_line_and_circle(
    fig: bokeh.plotting.Figure,
    source: ColumnDataSource,
    x_column_name: str,
    y_column_name: str,
    legend_label: str,
    color: Color,
    **kwargs,
) -> None:
    """
    線を引いて、プロットした部分に丸を付ける。

    Args:
        fig:
        source:
        x_column_name: sourceに対応するX軸の列名
        y_column_name: sourceに対応するY軸の列名
        legend_label:
        color: 線と点の色

    """

    fig.line(
        x=x_column_name,
        y=y_column_name,
        source=source,
        legend_label=legend_label,
        line_color=color,
        line_width=1,
        muted_alpha=0,
        muted_color=color,
        **kwargs,
    )
    fig.circle(
        x=x_column_name,
        y=y_column_name,
        source=source,
        legend_label=legend_label,
        muted_alpha=0.0,
        muted_color=color,
        color=color,
        **kwargs,
    )


def plot_moving_average(
    fig: bokeh.plotting.Figure,
    source: ColumnDataSource,
    x_column_name: str,
    y_column_name: str,
    legend_label: str,
    color: Color,
    **kwargs,
) -> None:
    """
    移動平均用にプロットする

    Args:
        fig:
        source:
        x_column_name: sourceに対応するX軸の列名
        y_column_name: sourceに対応するY軸の列名
        legend_label:
        color: 線と点の色

    """

    fig.line(
        x=x_column_name,
        y=y_column_name,
        source=source,
        legend_label=legend_label,
        line_color=color,
        line_width=1,
        line_dash="dashed",
        line_alpha=0.6,
        muted_alpha=0,
        muted_color=color,
        **kwargs,
    )


def create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
    """
    HoverTool用のオブジェクトを生成する。
    """
    if tool_tip_items is None:
        tool_tip_items = []

    detail_tooltips = [(e, f"@{{{e}}}") for e in tool_tip_items]
    hover_tool = HoverTool(tooltips=[("index", "$index"), ("(x,y)", "($x, $y)")] + detail_tooltips)
    return hover_tool


def get_plotted_user_id_list(
    user_id_list: List[str],
) -> List[str]:
    """
    グラフに表示するユーザのuser_idを生成する。最大値を超えていたら、超えている部分を切り捨てる。

    """
    if len(user_id_list) > MAX_USER_COUNT_FOR_LINE_GRAPH:
        logger.info(f"表示対象のuser_idの数が多いため、先頭から{MAX_USER_COUNT_FOR_LINE_GRAPH}個のみプロットします")

    return user_id_list[0:MAX_USER_COUNT_FOR_LINE_GRAPH]


class OutputTarget(Enum):
    ANNOTATION = "annotation"
    INPUT_DATA = "input_data"
    TASK = "task"


class LineGraph:
    """
    グラフを出力するクラス
    """

    #############################################
    # Field
    #############################################
    my_palette = bokeh.palettes.Category20[20]
    my_small_palette = bokeh.palettes.Category10[10]

    #############################################
    # Private
    #############################################

    def __init__(self, outdir: str):
        self.line_graph_outdir = outdir
        Path(self.line_graph_outdir).mkdir(exist_ok=True, parents=True)

    @staticmethod
    def _create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        Returns:

        """
        if tool_tip_items is None:
            tool_tip_items = []

        detail_tooltips = [(e, f"@{{{e}}}") for e in tool_tip_items]
        hover_tool = HoverTool(tooltips=[("index", "$index"), ("(x,y)", "($x, $y)")] + detail_tooltips)
        return hover_tool

    @staticmethod
    def _plot_line_and_circle(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_label: str,
        color: Color,
        **kwargs,
    ) -> None:
        """
        線を引いて、プロットした部分に丸を付ける。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label:
            color: 線と点の色

        """

        fig.line(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            muted_alpha=0,
            muted_color=color,
            **kwargs,
        )
        fig.circle(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            muted_alpha=0.0,
            muted_color=color,
            color=color,
            **kwargs,
        )

    @staticmethod
    def _plot_moving_average(
        fig: bokeh.plotting.Figure,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        legend_label: str,
        color: Color,
        **kwargs,
    ) -> None:
        """
        移動平均用にプロットする

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label:
            color: 線と点の色

        """

        fig.line(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            line_dash="dashed",
            line_alpha=0.6,
            muted_alpha=0,
            muted_color=color,
            **kwargs,
        )

    @staticmethod
    def _set_legend(fig: bokeh.plotting.Figure, hover_tool: HoverTool) -> None:
        """
        凡例の設定。

        Args:
            fig:
            hover_tool:
        """
        fig.add_tools(hover_tool)
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")

    def create_user_id_list(
        self,
        df: pandas.DataFrame,
        user_id_column: str,
        datetime_column: str,
        arg_user_id_list: Optional[List[str]] = None,
    ) -> List[str]:
        """
        グラフに表示するユーザのuser_idを生成する。

        Args:
            df:
            user_id_column: user_idが格納されている列の名前
            datetime_column: 日時列の降順でソートする
            arg_first_annotation_user_id_list: 指定されたuser_idのList

        Returns:
            グラフに表示するユーザのuser_idのList

        """
        max_user_length = len(self.my_palette)
        tmp_user_id_list: List[str] = (
            df.sort_values(by=datetime_column, ascending=False)[user_id_column].dropna().unique().tolist()
        )

        if arg_user_id_list is None or len(arg_user_id_list) == 0:
            user_id_list = tmp_user_id_list
        else:
            user_id_list = [user_id for user_id in tmp_user_id_list if user_id in arg_user_id_list]

        if len(user_id_list) > max_user_length:
            logger.info(f"表示対象のuser_idの数が多いため、先頭から{max_user_length}個のみグラフ化します")

        return user_id_list[0:max_user_length]

    def write_cumulative_line_graph_by_date(
        self, df: pandas.DataFrame, user_id_list: Optional[List[str]] = None
    ) -> None:
        """
        ユーザごとの作業時間を、日単位でプロットする。

        Args:
            user_id_list: プロットするユーザのuser_id


        """
        tooltip_item = [
            "user_id",
            "username",
            "date",
            "worktime_hour",
        ]

        if len(df) == 0:
            logger.info("データが0件のため出力ません。")
            return

        html_title = "累積折れ線-横軸_日-縦軸_作業時間"
        output_file = f"{self.line_graph_outdir}/{html_title}.html"

        user_id_list = self.create_user_id_list(df, "user_id", datetime_column="date", arg_user_id_list=user_id_list)
        if len(user_id_list) == 0:
            logger.info(f"作業しているユーザがいないため、{html_title} グラフは出力しません。")
            return

        logger.debug(f"{html_title} グラフに表示するユーザのuser_id = {user_id_list}")

        # 日付変換
        df["date_date"] = df["date"].map(lambda e: dateutil.parser.parse(e).date())

        fig_info_list = [
            dict(
                x="date_date",
                y="cumulative_worktime_hour",
                title="累積作業時間",
                x_axis_label="日",
                y_axis_label="作業時間[hour]",
            )
        ]

        logger.debug(f"{output_file} を出力します。")

        figs: List[bokeh.plotting.Figure] = []
        for fig_info in fig_info_list:
            figs.append(
                figure(
                    plot_width=1200,
                    plot_height=600,
                    title=fig_info["title"],
                    x_axis_label=fig_info["x_axis_label"],
                    x_axis_type="datetime",
                    y_axis_label=fig_info["y_axis_label"],
                )
            )

        for user_index, user_id in enumerate(user_id_list):
            filtered_df = df[df["user_id"] == user_id]
            if filtered_df.empty:
                logger.debug(f"dataframe is empty. user_id = {user_id}")
                continue

            source = ColumnDataSource(data=filtered_df)
            color = self.my_palette[user_index]
            username = filtered_df.iloc[0]["username"]

            for fig, fig_info in zip(figs, fig_info_list):
                self._plot_line_and_circle(
                    fig,
                    x_column_name=fig_info["x"],
                    y_column_name=fig_info["y"],
                    source=source,
                    legend_label=username,
                    color=color,
                )

        hover_tool = self._create_hover_tool(tooltip_item)
        for fig in figs:
            self._set_legend(fig, hover_tool)

        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=html_title)
        bokeh.plotting.save(bokeh.layouts.column(figs))

