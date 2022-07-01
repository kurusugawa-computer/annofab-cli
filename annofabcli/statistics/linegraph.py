"""
折れ線グラフを出力する関数の定義など
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from bokeh.core.properties import Color
from bokeh.models import Button, CheckboxGroup, CustomJS, GlyphRenderer, HoverTool
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)

MAX_USER_COUNT_FOR_LINE_GRAPH = 60
"""折れ線グラフにプロットできる最大のユーザ数"""


WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX = "__lastweek"
"""1週間移動平均を表す列名のsuffix"""


class LineGraph:
    """
    折れ線グラフに対応するクラス

    TODO: 引数にx_column, y_columnを受け取るのはよくないかもしれない
    """

    def __init__(
        self,
        *,
        title: str,
        x_axis_label: str,
        y_axis_label: str,
        x_column: str,
        y_column: str,
        plot_width: int = 1200,
        plot_height: int = 1000,
        tooltip_columns: Optional[list[str]] = None,
        **figure_kwargs,
    ) -> None:
        fig = figure(
            title=title,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
            plot_width=plot_width,
            plot_height=plot_height,
            **figure_kwargs,
        )
        hover_tool = create_hover_tool(tooltip_columns) if tooltip_columns is not None else None
        fig.add_tools(hover_tool)

        self.figure = fig
        self.x_column = x_column
        self.y_column = y_column

        required_columns = {x_column, y_column}
        if tooltip_columns is not None:
            required_columns = required_columns | set(tooltip_columns)
        self.required_columns = list(required_columns)

        self.line_glyphs: dict[str, GlyphRenderer] = {}
        self.marker_glyphs: dict[str, GlyphRenderer] = {}

    def add_line(
        self, source: ColumnDataSource, *, legend_label: str, color: Optional[Any] = None
    ) -> tuple[GlyphRenderer, GlyphRenderer]:
        """
        折れ線を追加する
        """

        line = self.figure.line(
            x=self.x_column,
            y=self.y_column,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
        )
        circle = self.figure.circle(
            x=self.x_column,
            y=self.y_column,
            source=source,
            legend_label=legend_label,
            color=color,
        )

        self.line_glyphs[legend_label] = line
        self.marker_glyphs[legend_label] = circle

        return (line, circle)

    def add_moving_average_line(
        self, source: ColumnDataSource, *, legend_label: str, color: Optional[Any] = None
    ) -> tuple[GlyphRenderer, GlyphRenderer]:
        """
        移動平均用の折れ線を追加する
        """

        line = self.figure.line(
            x=self.x_column,
            y=self.y_column,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            line_dash="dashed",
            line_alpha=0.6,
        )
        self.line_glyphs[legend_label] = line
        return line

    def config_legend(self) -> None:
        """
        折れ線を追加した後に、凡例の位置などを設定します。
        """
        fig = self.figure
        if len(fig.legend) == 0:
            return

        fig.legend.location = "top_left"
        fig.legend.click_policy = "hide"

        # 項目数が多いと、凡例に文字が入り切らないので、フォントサイズを小さくする
        if len(fig.legend.items) > 20:
            fig.legend.label_text_font_size = "9px"
            fig.legend.label_height = 10
            fig.legend.glyph_height = 10

        # グラフの左側に凡例を表示
        legend = fig.legend[0]
        fig.add_layout(legend, "left")

    def create_button_hiding_all_lines(self) -> Button:
        """
        全ての折れ線を非表示にするボタンを生成します。
        折れ線が20個以上あると見えづらくなるので、すべて非表示にするボタンを用意しました。
        """
        button = Button(label="すべての折れ線を非表示にする", button_type="primary")

        glyph_list: list[GlyphRenderer] = []
        glyph_list.extend(self.line_glyphs.values())
        glyph_list.extend(self.marker_glyphs.values())

        args = {"glyph_list": glyph_list}
        code = """
            for (let glyph of glyph_list) {
                glyph.visible = false
            }
        """
        button.js_on_click(CustomJS(code=code, args=args))
        return button

    def create_checkbox_displaying_markers(self) -> Button:
        """
        マーカーの表示/非表示を切り替えるチェックボックスを生成します。
        プロット数が多いと、マーカーによって見えづらくなるケースがあるため、表示/非表示を切り替えるチェックボックスを作成しました。
        """
        checkbox_group = CheckboxGroup(labels=["折れ線のマーカーを表示する"], active=[0])

        glyph_list = [e.glyph for e in self.marker_glyphs.values()]

        args = {"glyph_list": glyph_list}
        code = """
            let radius = ( "0" in this.active) ? null : 0
            for (let glyph of glyph_list) {
                glyph.radius = radius
            }
        """
        checkbox_group.js_on_click(CustomJS(code=code, args=args))
        return checkbox_group


def write_bokeh_graph(bokeh_obj, output_file: Path):
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)
    logger.debug(f"'{output_file}'を出力しました。")


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
    fig.legend.click_policy = "hide"
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
) -> list[GlyphRenderer]:
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
    result = []
    result.append(
        fig.line(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            **kwargs,
        )
    )
    result.append(
        fig.circle(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            color=color,
            **kwargs,
        )
    )
    return result


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
        **kwargs,
    )


def create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
    """
    HoverTool用のオブジェクトを生成する。
    """
    if tool_tip_items is None:
        tool_tip_items = []

    detail_tooltips = [(e, f"@{{{e}}}") for e in tool_tip_items]
    hover_tool = HoverTool(tooltips=[("(x,y)", "($x, $y)")] + detail_tooltips)
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
