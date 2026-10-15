from __future__ import annotations

import collections
import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import bokeh
import numpy
import pandas
from bokeh.models import LayoutDOM
from bokeh.models.widgets.markups import Div
from bokeh.plotting import figure

from annofabcli.annotation_zip.annotation_count import AnnotationCounter, AttributeNameKey, AttributeValueKey, GroupBy
from annofabcli.common.bokeh import convert_1d_figure_list_to_2d, create_pretext_from_metadata
from annofabcli.statistics.histogram import create_histogram_figure, get_bin_edges, get_sub_title_from_series

logger = logging.getLogger(__name__)

BIN_COUNT = 20


def _get_y_axis_label(group_by: GroupBy) -> str:
    if group_by == GroupBy.TASK_ID:
        return "タスク数"
    elif group_by == GroupBy.INPUT_DATA_ID:
        return "入力データ数"
    else:
        raise RuntimeError(f"group_by='{group_by}'が対象外です。")


def convert_to_2d_figure_list(figures_dict: dict[tuple[str, str], list[figure]], *, ncols: int = 4) -> list[list[LayoutDOM | None]]:
    """
    grid layout用に2次元のfigureリストに変換する。
    """
    row_list: list[list[LayoutDOM | None]] = []

    for (label_name, attribute_name), figure_list in figures_dict.items():
        row_list.append([Div(text=f"<h3>ラベル名='{label_name}', 属性名='{attribute_name}'</h3>")])

        for i in range(math.ceil(len(figure_list) / ncols)):
            start = i * ncols
            end = (i + 1) * ncols
            row: list[LayoutDOM | None] = []
            row.extend(figure_list[start:end])
            if len(row) < ncols:
                row.extend([None] * (ncols - len(row)))
            row_list.append(row)

    return row_list


def get_only_selective_attribute(columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
    """
    選択肢系の属性に対応する列のみ抽出する。
    属性値の個数が多い場合、非選択肢系の属性（トラッキングIDやアノテーションリンクなど）の可能性があるため、それらを除外する。
    CSVの列数を増やしすぎないための対策。
    """
    SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT = 20  # noqa: N806
    attribute_name_list: list[AttributeNameKey] = []
    for label, attribute_name, _ in columns:
        attribute_name_list.append((label, attribute_name))

    non_selective_attribute_names = {key for key, value in collections.Counter(attribute_name_list).items() if value > SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}

    if len(non_selective_attribute_names) > 0:
        logger.debug(f"以下の属性は値の個数が{SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}を超えていたため、集計しません。 :: {non_selective_attribute_names}")

    return [(label, attribute_name, attribute_value) for (label, attribute_name, attribute_value) in columns if (label, attribute_name) not in non_selective_attribute_names]


def plot_label_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: list[str] | None = None,
    bin_width: int | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    ラベルごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        bin_width: ビンの幅
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。
    """

    def create_df() -> pandas.DataFrame:
        all_label_key_set = {key for c in counter_list for key in c.annotation_count_by_label}
        if prior_keys is not None:
            remaining_columns = sorted(all_label_key_set - set(prior_keys))
            columns = prior_keys + remaining_columns
        else:
            columns = sorted(all_label_key_set)

        df = pandas.DataFrame([e.annotation_count_by_label for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)
        return df

    df = create_df()

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    y_axis_label = _get_y_axis_label(group_by)

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下のラベルは、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>アノテーション数の分布（ラベル名ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    logger.debug(f"{len(columns)}個のラベルごとのヒストグラムが描画されたhtmlファイルを出力します。")
    histogram_list: list[figure] = []
    for col in columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=str(col),
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        histogram_list.append(fig)

    figure_list_2d.extend(convert_1d_figure_list_to_2d(histogram_list))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()

    html_title = "アノテーション数の分布（ラベル名ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_attribute_histogram(  # noqa: PLR0915
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: list[AttributeValueKey] | None = None,
    bin_width: int | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    属性値ごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。

    """

    def create_df() -> pandas.DataFrame:
        all_key_set = {key for c in counter_list for key in c.annotation_count_by_attribute}
        if prior_keys is not None:
            remaining_columns = list(all_key_set - set(prior_keys))
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
            columns = prior_keys + remaining_columns_selective_attribute
        else:
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
            columns = remaining_columns_selective_attribute

        df = pandas.DataFrame([e.annotation_count_by_attribute for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)

        return df

    df = create_df()
    y_axis_label = _get_y_axis_label(group_by)

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下の属性値は、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>アノテーション数の分布（属性値ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    figures_dict = defaultdict(list)
    logger.debug(f"{len(columns)}個の属性値ごとのヒストグラムが描画されたhtmlファイルを出力します。")
    for col in columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名

        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=f"{col[0]},{col[1]},{col[2]}",
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        figures_dict[header].append(fig)

    figure_list_2d.extend(convert_to_2d_figure_list(figures_dict))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "アノテーション数の分布（属性値ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")
