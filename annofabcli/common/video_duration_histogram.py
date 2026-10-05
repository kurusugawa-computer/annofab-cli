from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

import bokeh
import numpy
import pandas
from bokeh.models import HoverTool, LayoutDOM
from bokeh.models.annotations.labels import Title
from bokeh.models.widgets.markups import PreText
from bokeh.plotting import ColumnDataSource, figure

from annofabcli.statistics.histogram import get_sub_title_from_series

logger = logging.getLogger(__name__)

BIN_COUNT = 20
"""指定がない場合のヒストグラムのビン数。"""


class TimeUnit(Enum):
    SECOND = "second"
    MINUTE = "minute"


def plot_video_duration(
    durations_for_input_data: Sequence[float],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: float | None = None,
    project_id: str | None = None,
    project_title: str | None = None,
    y_axis_label: str = "動画数",
    excluded_count: int | None = None,
) -> None:
    """
    動画長のヒストグラムを出力します。

    Args:
        durations_for_input_data: 動画の長さの一覧。単位は「秒」です。
        output_file: 出力先のファイルのパス
        time_unit: ヒストグラムに表示する時間の単位
        bin_width: ヒストグラムのビンの幅。単位は「秒」です。
        project_id: プロジェクトID。
        project_title: プロジェクト名。
        y_axis_label: 縦軸のラベル。
        excluded_count: 動画長が不明なため除外した件数。Noneなら表示しません。

    Returns:
        None。
    """

    def create_figure(
        durations: Sequence[float],
        bins: int | numpy.ndarray,
        histogram_range: tuple[float, float],
        title: str,
        x_axis_label: str,
        y_axis_label: str,
    ) -> figure:
        hist, bin_edges = numpy.histogram(durations, bins=bins, range=histogram_range)

        df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
        df_histogram["interval"] = [f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"], strict=False)]

        source = ColumnDataSource(df_histogram)
        fig = figure(  # type: ignore[call-arg]
            width=400,
            height=300,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
        )

        subtitle = get_sub_title_from_series(pandas.Series(durations), decimals=2) if durations else "対象0件"
        fig.add_layout(Title(text=subtitle, text_font_size="11px"), "above")
        fig.add_layout(Title(text=title), "above")

        hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

        fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

        fig.add_tools(hover)
        return fig

    if bin_width is not None and (not math.isfinite(bin_width) or bin_width <= 0):
        raise ValueError("--bin_widthには有限の正の値を指定してください。")

    if time_unit == TimeUnit.MINUTE:
        durations_for_input_data = [duration / 60 for duration in durations_for_input_data]

    if bin_width is not None:
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

        max_duration = max(durations_for_input_data, default=0)
        bins_sequence = numpy.arange(0, max_duration + bin_width, bin_width)

        if bins_sequence[-1] == max_duration:
            bins_sequence = numpy.append(bins_sequence, bins_sequence[-1] + bin_width)

        bins: int | numpy.ndarray = bins_sequence
    else:
        bins = BIN_COUNT

    x_axis_label = "動画の長さ[分]" if time_unit == TimeUnit.MINUTE else "動画の長さ[秒]"
    histogram_range = (min(durations_for_input_data, default=0), max(durations_for_input_data, default=0))

    description = f"project_id='{project_id}'\nproject_title='{project_title}'"
    if excluded_count is not None:
        description += f"\n集計単位: {y_axis_label}\n動画長が不明なため除外した件数: {excluded_count}件"
    layout_list: list[LayoutDOM] = [
        PreText(text=description),
        create_figure(
            durations_for_input_data,
            bins=bins,
            histogram_range=histogram_range,
            title="動画の長さの分布",
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
        ),
    ]

    bokeh_obj = bokeh.layouts.layout(layout_list)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    title = "動画の長さの分布"
    if project_title is not None:
        title = title + f"({project_title})"
    bokeh.plotting.output_file(output_file, title=title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")
