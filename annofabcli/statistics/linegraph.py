"""
折れ線グラフを出力する関数の定義など
"""
import logging
from pathlib import Path
from typing import List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from bokeh.core.properties import Color
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource

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
    """1週間移動平均用のpandas.Seriesを取得する。"""
    MOVING_WINDOW_DAYS = 7
    MIN_WINDOW_DAYS = 2
    return series.rolling(MOVING_WINDOW_DAYS, min_periods=MIN_WINDOW_DAYS).mean()


def get_weekly_sum(series: pandas.Series) -> pandas.Series:
    """1週間の合計値が格納されたpandas.Seriesを取得する。"""
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
