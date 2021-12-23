import logging
from typing import Optional

import numpy
import pandas
from bokeh.models import HoverTool, Title
from bokeh.plotting import ColumnDataSource, Figure, figure

logger = logging.getLogger(__name__)


def get_sub_title_from_series(ser: pandas.Series, decimals: int = 3) -> str:
    """pandas.Seriesから、平均値、標準偏差、データ数が記載されたSubTitleを生成する。"""
    mean = round(ser.mean(), decimals)
    std = round(ser.std(), decimals)
    sub_title = f"μ={mean}, α={std}, N={len(ser)}"
    return sub_title


def get_histogram_figure(
    ser: pandas.Series,
    x_axis_label: str,
    y_axis_label: str,
    title: str,
    sub_title: Optional[str] = None,
    plot_width: int = 400,
    plot_height: int = 300,
    bins: int = 20,
) -> Figure:
    hist, bin_edges = numpy.histogram(ser, bins)

    df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
    df_histogram["interval"] = [
        f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"])
    ]

    source = ColumnDataSource(df_histogram)
    fig = figure(
        plot_width=plot_width,
        plot_height=plot_height,
        x_axis_label=x_axis_label,
        y_axis_label=y_axis_label,
    )

    if sub_title is not None:
        fig.add_layout(Title(text=sub_title, text_font_size="11px"), "above")
    fig.add_layout(Title(text=title), "above")

    hover = HoverTool(tooltips=[("interval", "@interval"), ("frequency", "@frequency")])

    fig.quad(source=source, top="frequency", bottom=0, left="left", right="right", line_color="white")

    fig.add_tools(hover)
    return fig
