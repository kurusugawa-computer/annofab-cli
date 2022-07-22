"""
折れ線グラフを出力する関数の定義など
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, List, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import pandas
from bokeh.core.properties import Color
from bokeh.models import (
    Button,
    CheckboxGroup,
    CrosshairTool,
    CustomJS,
    DataRange1d,
    GlyphRenderer,
    HoverTool,
    LinearAxis,
)
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)

MAX_USER_COUNT_FOR_LINE_GRAPH = 60
"""折れ線グラフにプロットできる最大のユーザ数"""


WEEKLY_MOVING_AVERAGE_COLUMN_SUFFIX = "__lastweek"
"""1週間移動平均を表す列名のsuffix"""


class LineGraph:
    """
    折れ線グラフに対応するクラス

    Args:
        exists_secondary_y_axis
    """

    _SECONDARY_Y_RANGE_NAME = "secondary"
    """
    第2のY軸用の内部的な名前
    """

    @staticmethod
    def _create_hover_tool(tool_tip_items: Optional[List[str]] = None) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        """
        if tool_tip_items is None:
            tool_tip_items = []

        detail_tooltips = [(e, f"@{{{e}}}") for e in tool_tip_items]
        hover_tool = HoverTool(tooltips=[("(x,y)", "($x, $y)")] + detail_tooltips)
        return hover_tool

    def __init__(
        self,
        *,
        title: str,
        x_axis_label: str,
        y_axis_label: str,
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
        self.title = title
        self.tooltip_columns = tooltip_columns

        if tooltip_columns is not None:
            hover_tool = self._create_hover_tool(tooltip_columns)
            fig.add_tools(hover_tool)

        fig.add_tools(CrosshairTool())

        self.figure = fig

        self.exists_secondary_y_axis = False
        self.line_glyphs: dict[str, GlyphRenderer] = {}
        self.marker_glyphs: dict[str, GlyphRenderer] = {}

    def add_secondary_y_axis(
        self,
        axis_label: str,
        *,
        secondary_y_axis_range: Optional[DataRange1d] = None,
        primary_y_axis_range: Optional[DataRange1d] = None,
    ):
        """
        第2のY軸を追加する。

        Notes:
            軸範囲を設定する理由：第1軸と第2軸の軸範囲を指定しないと、第1軸と第2軸の軸範囲が同じになり、適切な軸範囲にならないため。
            https://qiita.com/yuji38kwmt/items/ccbee24184789686b102 参考

        Args:
            axis_label: 第2軸の名前
            secondary_y_axis_range: 第2Y軸の軸範囲
            primary_y_axis_range: 第1Y軸の軸範囲
        """
        self.figure.add_layout(
            LinearAxis(
                y_range_name=self._SECONDARY_Y_RANGE_NAME,
                axis_label=axis_label,
            ),
            "right",
        )
        if secondary_y_axis_range is not None:
            self.figure.extra_y_ranges = {self._SECONDARY_Y_RANGE_NAME: secondary_y_axis_range}
        else:
            self.figure.extra_y_ranges = {self._SECONDARY_Y_RANGE_NAME: DataRange1d()}

        if primary_y_axis_range is not None:
            self.figure.y_range = primary_y_axis_range

        self.exists_secondary_y_axis = True

    def add_line(
        self,
        source: ColumnDataSource,
        x_column: str,
        y_column: str,
        *,
        legend_label: str,
        color: Optional[Any] = None,
        is_secondary_y_axis: bool = False,
        **kwargs,
    ) -> tuple[GlyphRenderer, GlyphRenderer]:
        """
        折れ線を追加する

        is_secondary_y_axis
        """
        new_kwargs = copy.deepcopy(kwargs)
        if is_secondary_y_axis:
            new_kwargs["y_range_name"] = self._SECONDARY_Y_RANGE_NAME

        line = self.figure.line(
            x=x_column,
            y=y_column,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            **new_kwargs,
        )
        circle = self.figure.circle(
            x=x_column,
            y=y_column,
            source=source,
            legend_label=legend_label,
            color=color,
            **new_kwargs,
        )

        self.line_glyphs[legend_label] = line
        self.marker_glyphs[legend_label] = circle

        return (line, circle)

    def add_moving_average_line(
        self,
        source: ColumnDataSource,
        x_column: str,
        y_column: str,
        *,
        legend_label: str,
        color: Optional[Any] = None,
        is_secondary_y_axis: bool = False,
        **kwargs,
    ) -> tuple[GlyphRenderer, GlyphRenderer]:
        """
        移動平均用の折れ線を追加する
        """
        new_kwargs = copy.deepcopy(kwargs)
        if is_secondary_y_axis:
            new_kwargs["y_range_name"] = self._SECONDARY_Y_RANGE_NAME

        line = self.figure.line(
            x=x_column,
            y=y_column,
            source=source,
            legend_label=legend_label,
            line_color=color,
            line_width=1,
            line_dash="dashed",
            line_alpha=0.6,
            **new_kwargs,
        )

        self.line_glyphs[legend_label] = line
        return line

    def process_after_adding_glyphs(self) -> None:
        """
        折れ線などのGlyphを追加した後に実行する処理です。
        以下を設定します。
        * 凡例
        * 軸の範囲

        """
        self.configure_legend()

    def configure_legend(self):
        """
        凡例を設定します。

        Notes:
            折れ線などのGlyphを追加した後に実行する必要があります。

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

    def create_button_hiding_showing_all_lines(self, is_hiding: bool) -> Button:
        """
        全ての折れ線を非表示にするボタンを生成します。
        折れ線が20個以上あると見えづらくなるので、すべて非表示にするボタンを用意しました。

        Args:
            is_hiding: Trueなら非表示ボタンを生成します。
        """
        button_label = "すべての折れ線を非表示にする" if is_hiding else "すべての折れ線を表示する"

        button = Button(label=button_label, button_type="primary")

        glyph_list: list[GlyphRenderer] = []
        glyph_list.extend(self.line_glyphs.values())
        glyph_list.extend(self.marker_glyphs.values())

        args = {"glyph_list": glyph_list}
        str_is_visible = "false" if is_hiding else "true"
        code = f"for (let glyph of glyph_list) {{glyph.visible = {str_is_visible} }}"
        button.js_on_click(CustomJS(code=code, args=args))
        return button

    def create_checkbox_displaying_markers(self) -> CheckboxGroup:
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


def get_plotted_user_id_list(
    user_id_list: List[str],
) -> List[str]:
    """
    グラフに表示するユーザのuser_idを生成する。最大値を超えていたら、超えている部分を切り捨てる。

    """
    if len(user_id_list) > MAX_USER_COUNT_FOR_LINE_GRAPH:
        logger.info(f"表示対象のuser_idの数が多いため、先頭から{MAX_USER_COUNT_FOR_LINE_GRAPH}個のみプロットします")

    return user_id_list[0:MAX_USER_COUNT_FOR_LINE_GRAPH]
