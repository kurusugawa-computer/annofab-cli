from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Literal, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
from bokeh.models import CustomJS, HoverTool
from bokeh.models.annotations import Span
from bokeh.models.renderers.glyph_renderer import GlyphRenderer
from bokeh.models.widgets.inputs import MultiChoice
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


def write_bokeh_graph(bokeh_obj: Any, output_file: Path) -> None:  # noqa: ANN401
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)
    logger.debug(f"'{output_file}'を出力しました。")


def get_color_from_palette(index: int) -> str:
    my_palette = bokeh.palettes.Category10[10]
    return my_palette[index % len(my_palette)]


class ScatterGraph:
    DEFAULT_USER_TEXT_FONT_STYLE = "normal"

    DEFAULT_USER_TEXT_FONT_SIZE = "7pt"

    @staticmethod
    def create_hover_tool(tool_tip_items: list[str]) -> HoverTool:
        """
        HoverTool用のオブジェクトを生成する。
        """

        def exclude_phase_name(name: str) -> str:
            """
            tooltipに渡された名前から、最後のフェーズ名を除いた名前を返します。

            例えば"task_count_annotation"を渡すと"task_count"を返します。
            """
            tmp = name.split("_")
            return "_".join(tmp[0 : len(tmp) - 1])

        detail_tooltips = [(exclude_phase_name(e), f"@{{{e}}}") for e in tool_tip_items]
        hover_tool = HoverTool(tooltips=[("(x,y)", "($x, $y)"), *detail_tooltips])
        return hover_tool

    def __init__(
        self,
        *,
        title: str,
        x_axis_label: str,
        y_axis_label: str,
        width: int = 1200,
        height: int = 1000,
        tooltip_columns: Optional[list[str]] = None,
        **figure_kwargs,  # noqa: ANN003
    ) -> None:
        fig = figure(
            title=title,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
            width=width,
            height=height,
            **figure_kwargs,
        )
        self.title = title
        self.tooltip_columns = tooltip_columns
        if tooltip_columns is not None:
            hover_tool = self.create_hover_tool(tooltip_columns)
            self._hover_tool = hover_tool
            fig.add_tools(hover_tool)

        self.figure = fig

        self.finding_user_widget: Optional[MultiChoice] = None
        """ユーザーを探すためのWidget"""

        self.text_glyphs: dict[str, GlyphRenderer] = {}
        """key:user_id, value: 散布図に表示している名前のGlyph"""
        self._scatter_glyphs: dict[str, GlyphRenderer] = {}
        """key:biography, value: 散布図に表示している円形のGlyph"""

    def plot_average_line(self, value: float, dimension: Literal["width", "height"]) -> None:
        span_average_line = Span(
            location=value,
            dimension=dimension,
            line_color="red",
            line_width=0.5,
        )
        self.figure.add_layout(span_average_line)

    def plot_quartile_line(self, quartile: tuple[float, float, float], dimension: Literal["width", "height"]) -> None:
        """

        Args:
            fig (bokeh.plotting.Figure):
            quartile (tuple[float, float, float]): 四分位数。tuple[25%値, 50%値, 75%値]
            dimension (str): [description]: width or height
        """

        for value in quartile:
            span_average_line = Span(
                location=value,
                dimension=dimension,
                line_color="blue",
                line_width=0.5,
            )
            self.figure.add_layout(span_average_line)

    def plot_scatter(
        self,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        username_column_name: str,
        user_id_column_name: str,
        legend_label: str,
        color: str,
    ) -> None:
        """
        人ごとの情報を円形でプロットして、ユーザ名を表示する。

        Args:
            fig:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label: 凡例に表示する名前
            color: 線と点の色

        """
        if legend_label == "":
            legend_label = "none"

        self._scatter_glyphs[legend_label] = self.figure.scatter(x=x_column_name, y=y_column_name, source=source, legend_label=legend_label, color=color, muted_alpha=0.2, size=6)

        # 1点ごとに`text`で名前を表示している理由：
        # `add_multi_choice_widget_for_searching_user`関数で追加したMultiChoice Widgetで、名前の表示スタイルを変更するため
        for x, y, username, user_id in zip(source.data[x_column_name], source.data[y_column_name], source.data[username_column_name], source.data[user_id_column_name]):
            self.text_glyphs[user_id] = self.figure.text(
                x=x,
                y=y,
                # listで渡している理由: https://qiita.com/yuji38kwmt/items/5fad41f6db0090a80af4
                text=[username],
                legend_label=legend_label,
                text_font_style=self.DEFAULT_USER_TEXT_FONT_STYLE,
                text_font_size=self.DEFAULT_USER_TEXT_FONT_SIZE,
            )

    def plot_bubble(
        self,
        source: ColumnDataSource,
        x_column_name: str,
        y_column_name: str,
        username_column_name: str,
        user_id_column_name: str,
        size_column_name: str,
        legend_label: str,
        color: str,
        func_get_bubble_size: Callable[[Any], int],
    ) -> None:
        """
        バブルチャート用にプロットする。

        Args:
            source:
            x_column_name: sourceに対応するX軸の列名
            y_column_name: sourceに対応するY軸の列名
            legend_label: 凡例に表示する名前
            color: 線と点の色

        """

        if legend_label == "":
            legend_label = "none"

        tmp_size_field = f"__size__{size_column_name}"
        source.data[tmp_size_field] = numpy.array(list(map(func_get_bubble_size, source.data[size_column_name])))

        self._scatter_glyphs[legend_label] = self.figure.scatter(
            x=x_column_name,
            y=y_column_name,
            source=source,
            legend_label=legend_label,
            color=color,
            fill_alpha=0.5,
            muted_alpha=0.2,
            size=tmp_size_field,
        )

        # 1点ごとに`text`で名前を表示している理由：
        # `add_multi_choice_widget_for_searching_user`関数で追加したMultiChoice Widgetで、名前の表示スタイルを変更するため
        for x, y, username, user_id in zip(source.data[x_column_name], source.data[y_column_name], source.data[username_column_name], source.data[user_id_column_name]):
            self.text_glyphs[user_id] = self.figure.text(
                x=x,
                y=y,
                # listで渡している理由: https://qiita.com/yuji38kwmt/items/5fad41f6db0090a80af4
                text=[username],
                legend_label=legend_label,
                text_font_style=self.DEFAULT_USER_TEXT_FONT_STYLE,
                text_font_size=self.DEFAULT_USER_TEXT_FONT_SIZE,
                text_align="center",
                text_baseline="middle",
                muted_alpha=0.2,
            )

    def process_after_adding_glyphs(self) -> None:
        """
        散布図を追加した後に実行する処理です。
        以下を設定します。
        * 凡例

        """
        self.configure_legend()

        # 円形にカーソルを当てたときのみツールチップが表示されるようにする
        # 名前にカーソルを当てたときはツールチップが表示されないようにする。
        # 理由：名前の表示は`ColumnDataSource`を使っていない（`plot_scatter`メソッド参照）ため、ツールチップには値が"???"と表示される。
        # ユーザーが混乱しないようにするため、名前にカーソルを当てたときはツールチップが表示されないようにする。
        if self._hover_tool is not None and self._scatter_glyphs is not None:
            self._hover_tool.renderers = list(self._scatter_glyphs.values())  # type: ignore[assignment]

    def configure_legend(self):  # noqa: ANN201
        """
        凡例を設定します。

        Notes:
            散布図などのGlyphを追加した後に実行する必要があります。

        """
        fig = self.figure
        if len(fig.legend) == 0:
            return

        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        fig.legend.title = "biography"
        legend = fig.legend[0]
        fig.add_layout(legend, "left")

    def add_multi_choice_widget_for_searching_user(self, users: list[tuple[str, str]]) -> None:
        """
        特定のユーザーを探すためのMultiChoiceウィジェットを追加します。

        Args:
            users: ユーザーのリスト。tuple[user_id, username]
        Notes:
            2回以上実行しても意味がありません。

        """
        args = {"textGlyphs": self.text_glyphs}

        # 選択されたユーザーのフォントスタイルを太字にする
        code = """
        const selectedUserIds = this.value;
        for (let userId in textGlyphs) {
            if (selectedUserIds.includes(userId)) {
                textGlyphs[userId].glyph.text_font_style='bold';
                textGlyphs[userId].glyph.text_font_size='11pt';
            } else {
                textGlyphs[userId].glyph.text_font_style='%s';
                textGlyphs[userId].glyph.text_font_size='%s';
            }
        }
        """
        code = code % (self.DEFAULT_USER_TEXT_FONT_STYLE, self.DEFAULT_USER_TEXT_FONT_SIZE)
        options = [(user_id, f"{user_id}:{username}") for user_id, username in users]
        multi_choice = MultiChoice(options=options, title="Find User:", width=300)
        multi_choice.js_on_change(
            "value",
            CustomJS(code=code, args=args),
        )
        self.finding_user_widget = multi_choice

    @property
    def layout(self) -> bokeh.models.layouts.Row:
        widgets = []
        if self.finding_user_widget is not None:
            widgets.append(self.finding_user_widget)

        widgets_layout = bokeh.layouts.column(widgets)
        return bokeh.layouts.row([self.figure, widgets_layout])
