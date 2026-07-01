import logging
from dataclasses import dataclass

import numpy
import pandas
from bokeh.models import HoverTool
from bokeh.models.annotations.labels import Title
from bokeh.plotting import ColumnDataSource, figure

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistogramFrequencyColumn:
    """ヒストグラムの棒の高さとして表示する列情報。"""

    additional_columns: dict[str, numpy.ndarray]
    """切り替え用などで使う、度数以外の棒の高さ"""

    display_column: str
    """棒の高さとして表示する列名"""

    display_label: str
    """ツールチップに表示する棒の高さの名前"""


def get_sub_title_from_series(ser: pandas.Series, decimals: int = 3) -> str:
    """
    pandas.Seriesから、平均値、標準偏差(ddof=0)、データ数が記載されたSubTitleを生成する。
    """
    mean = round(ser.mean(), decimals)
    std = round(ser.std(ddof=0), decimals)
    sub_title = f"μ={mean}, α={std}, N={len(ser)}"
    return sub_title


def get_bin_edges(min_value: float, max_value: float, bin_width: float) -> numpy.ndarray:
    """
    numpy.histogramのbins引数に渡す、ビンの境界値を取得します。

    * min_value=0, max_value=3, bin_width=2の場合: [0, 2, 4]を返す。
    * min_value=0, max_value=4, bin_width=2の場合: [0, 2, 4, 6]を返す。

    Args:
        min_value: ヒストグラムに表示するデータの最小値
        max_value: ヒストグラムに表示するデータの最大値
        bin_width: ヒストグラムに表示するビンの幅
    """
    # stop引数に、`bin_width*2`を指定している理由：
    # 引数が小数のときは`len(bin_edges)``期待通りにならないときがあるので、ビンの数を少し増やしている
    # https://qiita.com/yuji38kwmt/items/ff00f3cb9083567d083f
    bin_edges = numpy.arange(start=min_value, stop=max_value + bin_width * 2, step=bin_width)  # type: ignore[call-overload]
    return bin_edges


def create_histogram_figure(
    hist: numpy.ndarray,
    bin_edges: numpy.ndarray,
    *,
    x_axis_label: str,
    y_axis_label: str,
    frequency_column: HistogramFrequencyColumn | None = None,
    title: str | None = None,
    sub_title: str | None = None,
    width: int = 400,
    height: int = 300,
) -> figure:
    """
    ヒストグラムのbokeh.figureを生成します。

    Args:
        hist: `numpy.histogram`の戻り値 tuple[0]
        bin_edges: `numpy.histogram`の戻り値 tuple[1]
        x_axis_label: X軸の名前
        y_axis_label: Y軸の名前
        frequency_column: ヒストグラムの棒の高さとして表示する列情報
        title: グラフのタイトル
        sub_title: グラフのサブタイトル
        width: グラフの幅
        height: グラフの高さ
    """
    df_histogram = pandas.DataFrame({"frequency": hist, "left": bin_edges[:-1], "right": bin_edges[1:]})
    display_column = "frequency"
    display_label = "frequency"
    if frequency_column is not None:
        df_histogram = df_histogram.assign(**frequency_column.additional_columns)
        display_column = frequency_column.display_column
        display_label = frequency_column.display_label
    df_histogram["interval"] = [f"{left:.1f} to {right:.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"], strict=False)]
    df_histogram["width"] = [f"{(right - left):.1f}" for left, right in zip(df_histogram["left"], df_histogram["right"], strict=False)]

    source = ColumnDataSource(df_histogram)
    fig = figure(  # type: ignore[call-arg]
        width=width,
        height=height,
        x_axis_label=x_axis_label,
        y_axis_label=y_axis_label,
    )

    if sub_title is not None:
        fig.add_layout(Title(text=sub_title, text_font_size="11px"), "above")
    if title is not None:
        fig.add_layout(Title(text=title), "above")

    hover = HoverTool(tooltips=[("interval", "@interval"), ("width", "@width"), (display_label, f"@{{{display_column}}}")])

    fig.quad(source=source, top=display_column, bottom=0, left="left", right="right", line_color="white")

    fig.add_tools(hover)
    return fig
