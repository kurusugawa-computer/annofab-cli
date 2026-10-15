from __future__ import annotations

import argparse
import collections
import json
import logging
import math
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

import bokeh
import numpy
import pandas
from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole, TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
from bokeh.models import LayoutDOM
from bokeh.models.widgets.markups import Div
from bokeh.plotting import figure
from dataclasses_json import DataClassJsonMixin, config

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_count import AnnotationSpecs
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_annotation import add_attribute_value_arguments, add_label_name_argument
from annofabcli.annotation_zip.visualize_annotation_count import convert_to_2d_figure_list, get_only_selective_attribute
from annofabcli.common.bokeh import convert_1d_figure_list_to_2d, create_pretext_from_metadata
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.statistics.histogram import create_histogram_figure, get_bin_edges, get_sub_title_from_series

# pylint: disable=too-many-lines


logger = logging.getLogger(__name__)

AttributeValueKey = tuple[str, str, str]
"""
属性のキー.
tuple[label_name_en, attribute_name_en, attribute_value] で表す。
"""

LabelKeys = Collection[str]

AttributeNameKey = tuple[str, str]
"""
属性名のキー.
tuple[label_name_en, attribute_name_en] で表す。
"""


AttributeKeys = Collection[Collection]


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


def encode_annotation_duration_second_by_attribute(
    annotation_duration_second_by_attribute: dict[AttributeValueKey, float],
) -> dict[str, dict[str, dict[str, float]]]:
    """annotation_duration_second_by_attributeを `{label_name: {attribute_name: {attribute_value: annotation_count}}}`のdictに変換します。
    JSONへの変換用関数です。
    """

    def _factory() -> collections.defaultdict:
        """入れ子の辞書を利用できるようにするための関数"""
        return collections.defaultdict(_factory)

    result: dict[str, dict[str, dict[str, float]]] = defaultdict(_factory)
    for (label_name, attribute_name, attribute_value), annotation_duration_second in annotation_duration_second_by_attribute.items():
        result[label_name][attribute_name][attribute_value] = annotation_duration_second
    return result


@dataclass(frozen=True)
class AnnotationDuration(DataClassJsonMixin):
    """
    入力データまたはタスク単位の区間アノテーションの長さ情報。
    """

    project_id: str
    task_id: str
    task_phase: TaskPhase
    task_phase_stage: int
    task_status: TaskStatus

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    video_duration_second: float | None
    """動画の長さ[秒]"""

    annotation_duration_second: float
    """
    区間アノテーションの合計の長さ（秒）
    `sum(annotation_duration_second_by_label.values())`と一致する
    """
    annotation_duration_second_by_label: dict[str, float]
    """
    ラベルごとの区間アノテーションの長さ（秒）
    key: ラベル名（英語）, value: 区間アノテーションの合計の長さ（秒）
    """
    annotation_duration_second_by_attribute: dict[AttributeValueKey, float] = field(
        metadata=config(
            encoder=encode_annotation_duration_second_by_attribute,
        )
    )
    """属性値ごとの区間アノテーションの長さ（秒）
    key: tuple[ラベル名(英語),属性名(英語),属性値(英語)], value: 区間アノテーションの合計の長さ（秒）
    """


class ListAnnotationDurationByInputData:
    """入力データ単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。

    Args:
        target_labels: 集計対象のラベル（label_name_en）
        target_attribute_names: 集計対象の属性名
        non_target_labels: 集計対象外のラベル
        non_target_attribute_names: 集計対象外の属性名のキー。
        frame_no_map: key:task_id,input_data_idのtuple, value:フレーム番号

    """

    def __init__(
        self,
        *,
        target_labels: Collection[str] | None = None,
        non_target_labels: Collection[str] | None = None,
        target_attribute_names: Collection[AttributeNameKey] | None = None,
        non_target_attribute_names: Collection[AttributeNameKey] | None = None,
    ) -> None:
        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None

    def get_annotation_duration(self, simple_annotation: dict[str, Any], video_duration_second: float | None = None) -> AnnotationDuration:
        """
        1個のアノテーションJSONに対して、ラベルごと/属性ごとの区間アノテーションの長さを取得する。

        Args:
            simple_annotation: アノテーションJSONファイルの内容
            video_duration_second: 動画の長さ[秒]
        """

        def calculate_annotation_duration_second(detail: dict[str, Any]) -> float:
            """区間アノテーションのdetail情報から、区間アノテーションの長さ（秒）を計算する"""
            return (detail["data"]["end"] - detail["data"]["begin"]) / 1000

        def convert_attribute_value_to_key(value: bool | str | float) -> str:  # noqa: FBT001
            """
            アノテーションJSONに格納されている属性値を、dict用のkeyに変換する。

            Notes:
                アノテーションJSONに格納されている属性値の型はbool, str, floatの3つ

            """
            if isinstance(value, bool):
                # str関数で変換せずに、直接文字列を返している理由：
                # bool値をstr関数に渡すと、`True/False`が返る。
                # CSVの列名やJSONのキーとして扱う場合、`True/False`だとPythonに依存した表現に見えるので、`true/false`に変換する
                if value:
                    return "true"
                elif not value:
                    return "false"
            return str(value)

        # 区間アノテーションのみのdetails
        # TODO type文字列の定義をannofab-apiに定義する
        range_details = [e for e in simple_annotation["details"] if e["data"]["_type"] == "Range"]

        annotation_duration_by_label: dict[str, float] = defaultdict(float)
        for detail in range_details:
            annotation_duration_by_label[detail["label"]] += calculate_annotation_duration_second(detail)

        if self.target_labels is not None:
            annotation_duration_by_label = {label: duration for label, duration in annotation_duration_by_label.items() if label in self.target_labels}

        if self.non_target_labels is not None:
            annotation_duration_by_label = {label: duration for label, duration in annotation_duration_by_label.items() if label not in self.non_target_labels}

        annotation_duration_by_attribute: dict[AttributeValueKey, float] = defaultdict(float)
        for detail in range_details:
            label = detail["label"]
            if label not in annotation_duration_by_label:
                # 対象外のラベルは除外する
                continue

            for attribute, value in detail["attributes"].items():
                attribute_key = (label, attribute, convert_attribute_value_to_key(value))
                annotation_duration_by_attribute[attribute_key] += calculate_annotation_duration_second(detail)

        if self.target_attribute_names is not None:
            annotation_duration_by_attribute = {
                (label, attribute_name, attribute_value): duration
                for (label, attribute_name, attribute_value), duration in annotation_duration_by_attribute.items()
                if (label, attribute_name) in self.target_attribute_names
            }

        if self.non_target_attribute_names is not None:
            annotation_duration_by_attribute = {
                (label, attribute_name, attribute_value): duration
                for (label, attribute_name, attribute_value), duration in annotation_duration_by_attribute.items()
                if (label, attribute_name) not in self.non_target_attribute_names
            }

        return AnnotationDuration(
            project_id=simple_annotation["project_id"],
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            updated_datetime=simple_annotation["updated_datetime"],
            video_duration_second=video_duration_second,
            annotation_duration_second=sum(annotation_duration_by_label.values()),
            annotation_duration_second_by_label=annotation_duration_by_label,
            annotation_duration_second_by_attribute=annotation_duration_by_attribute,
        )

    def get_annotation_duration_list(
        self,
        annotation_path: Path,
        *,
        input_data_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> list[AnnotationDuration]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとの区間アノテーションの長さを取得する。

        Args:
            input_data_json_path: 入力データ全件ファイルのパス。動画の長さを取得するのに利用します。
        """
        dict_input_data: dict[str, dict[str, Any]] | None = None
        if input_data_json_path is not None:
            with input_data_json_path.open() as f:
                input_data_list = json.load(f)
            dict_input_data = {e["input_data_id"]: e for e in input_data_list}

        annotation_duration_list = []

        target_task_ids = set(target_task_ids) if target_task_ids is not None else None

        iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)

        logger.debug("アノテーションzip/ディレクトリを読み込み中")
        for index, parser in enumerate(iter_parser):
            if (index + 1) % 1000 == 0:
                logger.debug(f"{index + 1}  件目のJSONを読み込み中")

            if target_task_ids is not None and parser.task_id not in target_task_ids:
                continue

            simple_annotation_dict = parser.load_json()
            if task_query is not None:  # noqa: SIM102
                if not match_annotation_with_task_query(simple_annotation_dict, task_query):
                    continue

            video_duration_second: float | None = None
            if dict_input_data is not None:
                input_data = dict_input_data[parser.input_data_id]
                video_duration_second = input_data["system_metadata"]["input_duration"]

            annotation_duration = self.get_annotation_duration(simple_annotation_dict, video_duration_second=video_duration_second)
            annotation_duration_list.append(annotation_duration)

        return annotation_duration_list


BIN_COUNT = 20
"""ヒストグラムのビンの個数"""


class TimeUnit(Enum):
    """ヒストグラムに表示する時間の単位。"""

    SECOND = "second"
    """秒。"""
    MINUTE = "minute"
    """分。"""


def plot_annotation_duration_histogram_by_label(  # noqa: PLR0915
    annotation_duration_list: list[AnnotationDuration],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: float | None = None,
    prior_keys: list[str] | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    ラベルごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        annotation_duration_list: タスクごとの区間アノテーションの長さ。
        output_file: 出力先HTMLファイル。
        time_unit: ヒストグラムに表示する時間の単位
        bin_width: ビンの幅（単位は秒）
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。

    Returns:
        None。
    """

    def create_df() -> pandas.DataFrame:
        """対象系列の長さを表示単位に変換します。

        Args:
            なし。

        Returns:
            タスクごとの長さのDataFrame。
        """
        all_label_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_label.keys()}  # noqa: SIM118
        if prior_keys is not None:
            remaining_columns = sorted(all_label_key_set - set(prior_keys))
            columns = prior_keys + remaining_columns
        else:
            columns = sorted(all_label_key_set)

        df = pandas.DataFrame([e.annotation_duration_second_by_label for e in annotation_duration_list], columns=columns)
        df.fillna(0, inplace=True)
        if time_unit == TimeUnit.MINUTE:
            df = df / 60
        return df

    def get_histogram_range(df: pandas.DataFrame) -> tuple[float, float] | None:
        """範囲をそろえる場合にデータ全体の範囲を返します。

        Args:
            df: 対象系列の長さ。

        Returns:
            最小値と最大値。範囲をそろえない場合はNone。
        """
        if arrange_bin_edge:
            return (
                df.min(numeric_only=True).min(),
                df.max(numeric_only=True).max(),
            )
        return None

    df = create_df()
    if df.empty:
        # 対象タスクが0件の場合は見出しとメタデータのみを出力します。
        df = df.iloc[:, :0]
    histogram_list: list[figure] = []

    max_duration = df.max(numeric_only=True).max()

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>区間アノテーションの長さの分布（ラベル名ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下の属性値は、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
        df = df[columns]

    if bin_width is not None:  # noqa: SIM102
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

    x_axis_label = "区間アノテーションの長さ[分]" if time_unit == TimeUnit.MINUTE else "区間アノテーションの長さ[秒]"
    histogram_range = get_histogram_range(df)

    logger.debug(f"{len(df.columns)}個のラベルごとのヒストグラムを出力します。")
    for col in df.columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_duration, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label=x_axis_label,
            y_axis_label="タスク数",
            title=str(col),
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        histogram_list.append(fig)

    figure_list_2d.extend(convert_1d_figure_list_to_2d(histogram_list))

    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "区間アノテーションの長さの分布（ラベル名ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_annotation_duration_histogram_by_attribute(  # noqa: PLR0915
    annotation_duration_list: Sequence[AnnotationDuration],
    output_file: Path,
    *,
    time_unit: TimeUnit,
    bin_width: float | None = None,
    prior_keys: list[AttributeValueKey] | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    属性値ごとの区間アノテーションの長さのヒストグラムを出力します。

    Args:
        annotation_duration_list: タスクごとの区間アノテーションの長さ。
        output_file: 出力先HTMLファイル。
        time_unit: ヒストグラムに表示する時間の単位。
        bin_width: ビンの幅（単位は秒）
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムは生成しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。

    Returns:
        None。
    """

    def create_df() -> pandas.DataFrame:
        """対象系列の長さを表示単位に変換します。

        Args:
            なし。

        Returns:
            タスクごとの長さのDataFrame。
        """
        all_key_set = {key for c in annotation_duration_list for key in c.annotation_duration_second_by_attribute.keys()}  # noqa: SIM118
        if prior_keys is not None:
            remaining_columns = list(all_key_set - set(prior_keys))
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
            columns = prior_keys + remaining_columns_selective_attribute
        else:
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
            columns = remaining_columns_selective_attribute

        df = pandas.DataFrame([e.annotation_duration_second_by_attribute for e in annotation_duration_list], columns=columns)
        df.fillna(0, inplace=True)
        if time_unit == TimeUnit.MINUTE:
            df = df / 60
        return df

    def get_histogram_range(df: pandas.DataFrame) -> tuple[float, float] | None:
        """範囲をそろえる場合にデータ全体の範囲を返します。

        Args:
            df: 対象系列の長さ。

        Returns:
            最小値と最大値。範囲をそろえない場合はNone。
        """
        if arrange_bin_edge:
            return (
                df.min(numeric_only=True).min(),
                df.max(numeric_only=True).max(),
            )
        return None

    df = create_df()
    if df.empty:
        # 対象タスクが0件の場合は見出しとメタデータのみを出力します。
        df = df.iloc[:, :0]
    logger.debug(f"{len(df.columns)}個の属性値ごとのヒストグラムで出力します。")

    if bin_width is not None:  # noqa: SIM102
        if time_unit == TimeUnit.MINUTE:
            bin_width = bin_width / 60

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下のラベルは、すべてのタスクで区間アノテーションの長さが0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
        df = df[columns]

    histogram_range = get_histogram_range(df)
    max_duration = df.max(numeric_only=True).max()
    x_axis_label = "区間アノテーションの長さ[分]" if time_unit == TimeUnit.MINUTE else "区間アノテーションの長さ[秒]"

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>区間アノテーションの長さの分布（属性値ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    figures_dict = defaultdict(list)
    for col in df.columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名

        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_duration, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label=x_axis_label,
            y_axis_label="タスク数",
            title=f"{col[0]},{col[1]},{col[2]}",
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )

        figures_dict[header].append(fig)

    figure_list_2d.extend(convert_to_2d_figure_list(figures_dict))

    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "区間アノテーションの長さの分布（属性値ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"
    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


@dataclass
class DurationPlotData:
    """ヒストグラム用の長さ情報と表示順。"""

    durations: list[AnnotationDuration]
    """タスクごとの区間アノテーションの長さ。"""
    label_keys: list[str]
    """ラベルの表示順。"""
    attribute_keys: list[AttributeValueKey]
    """属性値の表示順。"""


def get_duration_plot_data(
    annotation_path: Path,
    specs: AnnotationSpecs,
    args: argparse.Namespace,
    translator: AnnotationNameTranslator | None = None,
) -> DurationPlotData:
    """対象の名称を絞り込み、日本語名へ変換した描画データを作ります。

    Args:
        annotation_path: ZIPまたは展開済みディレクトリ。
        specs: 区間アノテーションの仕様。
        args: コマンドライン引数。
        translator: 日本語名への変換。

    Returns:
        描画データと表示順。
    """
    labels = specs.label_keys()
    if args.label_name is not None:
        labels, unknown = specs.get_label_keys_by_label_names(annofabcli.common.cli.get_list_from_args(args.label_name))
        if unknown:
            logger.warning(f"アノテーション仕様にないラベル名: {unknown}")
    attributes = specs.selective_attribute_name_keys()
    if args.by_attribute:
        names = args.attribute_name if args.attribute_name is not None else args.additional_attribute_name
        if names is not None:
            specified, unknown = specs.get_attribute_name_keys_by_attribute_names(annofabcli.common.cli.get_list_from_args(names))
            if unknown:
                logger.warning(f"アノテーション仕様にない属性名: {unknown}")
            attributes = specified if args.attribute_name is not None else list(dict.fromkeys([*attributes, *specified]))
    attributes = [key for key in attributes if key[0] in labels]
    durations = ListAnnotationDurationByInputData(
        target_labels=labels if args.label_name is not None else None,
        target_attribute_names=attributes,
    ).get_annotation_duration_list(
        annotation_path,
        target_task_ids=annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None,
        task_query=TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None,
    )
    if len({(e.project_id, e.task_id) for e in durations}) != len(durations):
        raise AnnofabCliException("入力データが複数あるタスクが含まれています。動画タスクを指定してください。")
    attribute_keys = list(
        dict.fromkeys(
            [
                *specs.get_attribute_value_keys_for_target_attributes(attributes),
                *sorted({key for duration in durations for key in duration.annotation_duration_second_by_attribute}),
            ]
        )
    )
    if translator is not None:
        translated = []
        for duration in durations:
            label_values: dict[str, float] = defaultdict(float)
            attribute_values: dict[AttributeValueKey, float] = defaultdict(float)
            for label, value in duration.annotation_duration_second_by_label.items():
                label_values[translator.label_name(label)] += value
            for key, value in duration.annotation_duration_second_by_attribute.items():
                attribute_values[translator.attribute_value_key(key)] += value
            translated.append(replace(duration, annotation_duration_second_by_label=dict(label_values), annotation_duration_second_by_attribute=dict(attribute_values)))
        durations = translated
        labels = list(dict.fromkeys(translator.label_name(label) for label in labels))
        attribute_keys = list(dict.fromkeys(translator.attribute_value_key(key) for key in attribute_keys))
    return DurationPlotData(durations, labels, attribute_keys)


class VisualizeAnnotationDuration(CommandLine):
    """タスクごとの区間アノテーションの長さを可視化します。"""

    def main(self) -> None:
        """必要な入力を取得し、HTMLファイルを出力します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        self.require_project_access(args.project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project, _ = self.service.api.get_project(args.project_id)
        if project["input_data_type"] != InputDataType.MOVIE.value:
            raise AnnofabCliException("動画プロジェクトを指定してください。")
        specs = AnnotationSpecs(self.service, args.project_id, annotation_type=DefaultAnnotationType.RANGE.value)
        translator = AnnotationNameTranslator.from_project(self.service, args.project_id) if args.use_japanese_name else None
        with tempfile.TemporaryDirectory() as directory:
            annotation_path = args.annotation
            if annotation_path is None:
                annotation_path = DownloadingFile(self.service).download_annotation_zip_to_dir(args.project_id, args.temp_dir if args.temp_dir is not None else Path(directory), is_latest=args.latest)
            data = get_duration_plot_data(annotation_path, specs, args, translator)
        metadata = {
            "project_id": args.project_id,
            "project_title": project["title"],
            "task_query": annofabcli.common.cli.get_json_from_args(args.task_query) if args.task_query is not None else None,
            "target_task_ids": annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None,
        }
        logger.info(f"{len(data.durations)}件のタスクの区間アノテーションの長さを可視化します。")
        if args.by_attribute:
            plot_annotation_duration_histogram_by_attribute(
                data.durations,
                output_file=Path(args.output),
                time_unit=TimeUnit(args.time_unit),
                bin_width=args.bin_width,
                prior_keys=data.attribute_keys,
                exclude_empty_value=args.exclude_empty_value,
                arrange_bin_edge=args.arrange_bin_edge,
                metadata=metadata,
            )
        else:
            plot_annotation_duration_histogram_by_label(
                data.durations,
                output_file=Path(args.output),
                time_unit=TimeUnit(args.time_unit),
                bin_width=args.bin_width,
                prior_keys=data.label_keys,
                exclude_empty_value=args.exclude_empty_value,
                arrange_bin_edge=args.arrange_bin_edge,
                metadata=metadata,
            )


def main(args: argparse.Namespace) -> None:
    """ビン幅を検証して可視化コマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    if args.bin_width is not None and (not math.isfinite(args.bin_width) or args.bin_width <= 0):
        raise AnnofabCliException("--bin_widthには正の有限な秒数を指定してください。")
    service = build_annofabapi_resource_and_login(args)
    VisualizeAnnotationDuration(service, AnnofabApiFacade(service), args).main()


def add_arguments(parser: argparse.ArgumentParser, *, by_attribute: bool) -> None:
    """区間長の可視化コマンドの引数を登録します。

    Args:
        parser: 引数パーサー。
        by_attribute: 属性値ごとの可視化か。

    Returns:
        None。
    """
    arguments = ArgumentParser(parser)
    arguments.add_project_id()
    parser.add_argument("--annotation", type=Path, help="アノテーションZIPまたは展開済みディレクトリ。省略するとダウンロードします。")
    arguments.add_output(required=True, help_message="出力先HTMLファイルのパスを指定します。")
    parser.add_argument("--time_unit", choices=[e.value for e in TimeUnit], default=TimeUnit.SECOND.value, help="ヒストグラムに表示する時間の単位。")
    parser.add_argument("--bin_width", type=float, help="ビンの幅を正の秒数で指定します。表示単位が分でも秒で指定します。省略するとビンの個数が20になるように調整します。")
    parser.add_argument("--exclude_empty_value", action="store_true", help="すべてのタスクで区間長が0のヒストグラムを描画しません。")
    parser.add_argument("--arrange_bin_edge", action="store_true", help="各ヒストグラムの範囲とビン幅をそろえます。")
    arguments.add_task_id(required=False)
    parser.add_argument("--task_query", "-tq", help="対象タスクの条件をJSONで指定します。キーはtask_id, status, phase, phase_stageです。file://でファイルを指定できます。")
    parser.add_argument("--latest", action="store_true", help="ZIPのダウンロード時に最新のアノテーションZIPを取得します。数分待つ場合があります。")
    parser.add_argument("--temp_dir", type=Path, help="アノテーションZIPのダウンロード先ディレクトリ。")
    add_use_japanese_name_argument(parser)
    if by_attribute:
        add_attribute_value_arguments(parser)
    else:
        add_label_name_argument(parser, target_description="区間アノテーション")
    parser.set_defaults(subcommand_func=main, by_attribute=by_attribute)
