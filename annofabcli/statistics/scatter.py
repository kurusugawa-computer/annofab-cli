from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Callable, Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
from bokeh.core.properties import Color
from bokeh.models import HoverTool
from bokeh.plotting import ColumnDataSource

logger = logging.getLogger(__name__)


def write_bokeh_graph(bokeh_obj, output_file: Path):
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    bokeh.plotting.output_file(output_file, title=output_file.stem)
    bokeh.plotting.save(bokeh_obj)
    logger.debug(f"'{output_file}'を出力しました。")


def get_color_from_palette(index: int) -> Color:
    my_palette = bokeh.palettes.Category10[10]
    return my_palette[index % len(my_palette)]


def plot_bubble(
    fig: bokeh.plotting.Figure,
    source: ColumnDataSource,
    x_column_name: str,
    y_column_name: str,
    text_column_name: str,
    size_column_name: str,
    legend_label: str,
    color: Any,
    func_get_bubble_size: Optional[Callable[[Any], int]] = None,
) -> None:
    """
    バブルチャート用にプロットする。

    Args:
        fig:
        source:
        x_column_name: sourceに対応するX軸の列名
        y_column_name: sourceに対応するY軸の列名
        legend_label: 凡例に表示する名前
        color: 線と点の色

    """

    def _worktime_hour_to_scatter_size(worktime_hour: float) -> int:
        """
        作業時間からバブルの大きさに変更する。
        """
        MIN_SCATTER_SIZE = 4
        if worktime_hour <= 0:
            return MIN_SCATTER_SIZE
        tmp = int(math.log2(worktime_hour) * 15 - 50)
        if tmp < MIN_SCATTER_SIZE:
            return MIN_SCATTER_SIZE
        else:
            return tmp

    if func_get_bubble_size is None:
        func_get_bubble_size = _worktime_hour_to_scatter_size

    if legend_label == "":
        legend_label = "none"

    tmp_size_field = f"__size__{size_column_name}"
    source.data[tmp_size_field] = numpy.array(list(map(func_get_bubble_size, source.data[size_column_name])))
    fig.scatter(
        x=x_column_name,
        y=y_column_name,
        source=source,
        legend_label=legend_label,
        color=color,
        fill_alpha=0.5,
        muted_alpha=0.2,
        size=tmp_size_field,
    )
    fig.text(
        x=x_column_name,
        y=y_column_name,
        source=source,
        text=text_column_name,
        text_align="center",
        text_baseline="middle",
        text_font_size="7pt",
        legend_label=legend_label,
        muted_alpha=0.2,
    )


def plot_scatter(
    fig: bokeh.plotting.Figure,
    source: ColumnDataSource,
    x_column_name: str,
    y_column_name: str,
    text_column_name: str,
    legend_label: str,
    color: Any,
) -> None:
    """
    丸でプロットして、ユーザ名を表示する。

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

    fig.circle(x=x_column_name, y=y_column_name, source=source, legend_label=legend_label, color=color, muted_alpha=0.2)
    fig.text(
        x=x_column_name,
        y=y_column_name,
        source=source,
        text=text_column_name,
        text_font_size="7pt",
        legend_label=legend_label,
        muted_alpha=0.2,
    )


def create_hover_tool(tool_tip_items: list[str]) -> HoverTool:
    """
    HoverTool用のオブジェクトを生成する。
    """

    def exclude_phase_name(name: str) -> str:
        tmp = name.split("_")
        return "_".join(tmp[0 : len(tmp) - 1])

    detail_tooltips = [(exclude_phase_name(e), f"@{{{e}}}") for e in tool_tip_items]
    hover_tool = HoverTool(tooltips=detail_tooltips)
    return hover_tool
