from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Literal, Protocol, assert_never, cast

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip,
    lazy_parse_simple_annotation_zip_by_task,
)
from annofabapi.pydantic_models.additional_data_definition_type import AdditionalDataDefinitionType
from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus
from dataclasses_json import DataClassJsonMixin, config

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_aggregation import (
    INPUT_DATA_ID_GROUP,
    TASK_ID_GROUP,
    CountSummary,
    aggregate_task_counts,
    is_summary_group,
    needs_task_metadata,
    validate_group_by,
)
from annofabcli.annotation_zip.task_metadata import TASK_METADATA_COLUMN_PREFIX, get_task_metadata_by_task_id, get_task_metadata_keys
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json
from annofabcli.statistics.list_annotation_count import AnnotationSpecs

logger = logging.getLogger(__name__)


AttributeValueType = Literal["filled", "empty"]
AttributeValueKey = tuple[str, str, AttributeValueType]
"""
属性のキー.
tuple[label_name_en, attribute_name_en, filled | empty] で表す。
"""


AttributeNameKey = tuple[str, str]
"""
属性名のキー.
tuple[label_name_en, attribute_name_en] で表す。
"""


AttributeKeys = Collection[Collection]


class HasAnnotationAttributeCounts(Protocol):
    annotation_attribute_counts: dict[AttributeValueKey, int]


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


def encode_annotation_count_by_attribute(
    annotation_count_by_attribute: dict[AttributeValueKey, int],
) -> dict[str, dict[str, dict[str, int]]]:
    """annotation_duration_second_by_attributeを `{label_name: {attribute_name: {attribute_value: annotation_count}}}`のdictに変換します。
    JSONへの変換用関数です。
    """

    def _factory() -> collections.defaultdict:
        """入れ子の辞書を利用できるようにするための関数"""
        return collections.defaultdict(_factory)

    result: dict[str, dict[str, dict[str, int]]] = defaultdict(_factory)
    for (label_name, attribute_name, attribute_value_type), annotation_count in annotation_count_by_attribute.items():
        result[label_name][attribute_name][attribute_value_type] = annotation_count
    return result


@dataclass(frozen=True)
class AnnotationCountByInputData(DataClassJsonMixin, HasAnnotationAttributeCounts):
    """
    入力データ単位のアノテーション数の情報。
    """

    project_id: str
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    annotation_attribute_counts: dict[AttributeValueKey, int] = field(
        metadata=config(
            encoder=encode_annotation_count_by_attribute,
        )
    )
    """属性値ごとのアノテーションの個数
    key: tuple[ラベル名(英語),属性名(英語),属性値の種類], value: アノテーション数
    """
    frame_no: int | None = None
    """フレーム番号（1始まり）。アノテーションJSONには含まれていない情報なので、Optionalにする"""
    task_metadata: dict[str, Any] = field(default_factory=dict)
    """出力対象とするタスクメタデータ。"""


@dataclass(frozen=True)
class AnnotationCountByTask(DataClassJsonMixin, HasAnnotationAttributeCounts):
    """
    タスク単位のアノテーション数の情報。
    """

    project_id: str
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    input_data_count: int
    annotation_attribute_counts: dict[AttributeValueKey, int] = field(
        metadata=config(
            encoder=encode_annotation_count_by_attribute,
        )
    )
    """属性値ごとのアノテーションの個数
    key: tuple[ラベル名(英語),属性名(英語),属性値の種類], value: アノテーション数
    """
    task_metadata: dict[str, Any] = field(default_factory=dict)
    """出力対象とするタスクメタデータ。"""


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


def lazy_parse_simple_annotation_by_task(annotation_path: Path) -> Iterator[SimpleAnnotationParserByTask]:
    """アノテーションをタスク単位で遅延パースします。

    Args:
        annotation_path: アノテーションzipまたは展開したディレクトリ。

    Returns:
        タスク単位のパーサー。

    Raises:
        RuntimeError: パスが存在しないか、サポート対象外の場合。
    """
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")
    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir_by_task(annotation_path)
    if zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip_by_task(annotation_path)
    raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


def convert_annotation_count_list_by_input_data_to_by_task(annotation_count_list: list[AnnotationCountByInputData]) -> list[AnnotationCountByTask]:
    """
    入力データ単位のアノテーション数情報をタスク単位のアノテーション数情報に変換する
    """
    tmp_dict: dict[str, list[AnnotationCountByInputData]] = collections.defaultdict(list)
    for annotation_count in annotation_count_list:
        tmp_dict[annotation_count.task_id].append(annotation_count)

    result = []
    for task_id, annotation_count_list_by_input_data in tmp_dict.items():
        first_elm = annotation_count_list_by_input_data[0]
        input_data_count = len(annotation_count_list_by_input_data)

        annotation_attribute_counts: dict[AttributeValueKey, int] = defaultdict(int)
        for elm in annotation_count_list_by_input_data:
            for key, value in elm.annotation_attribute_counts.items():
                annotation_attribute_counts[key] += value

        result.append(
            AnnotationCountByTask(
                project_id=first_elm.project_id,
                task_id=task_id,
                task_status=first_elm.task_status,
                task_phase=first_elm.task_phase,
                task_phase_stage=first_elm.task_phase_stage,
                input_data_count=input_data_count,
                task_metadata=first_elm.task_metadata,
                annotation_attribute_counts=annotation_attribute_counts,
            )
        )
    return result


class ListAnnotationCounterByInputData:
    """入力データ単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。

    Args:
        target_labels: 集計対象のラベル（label_name_en）
        target_attribute_names: 集計対象の属性名
        non_target_labels: 集計対象外のラベル
        non_target_attribute_names: 集計対象外の属性名のキー。

    """

    def __init__(
        self,
        *,
        target_labels: Collection[str] | None = None,
        non_target_labels: Collection[str] | None = None,
        target_attribute_names: Collection[AttributeNameKey] | None = None,
        non_target_attribute_names: Collection[AttributeNameKey] | None = None,
        frame_no_map: dict[tuple[str, str], int] | None = None,
    ) -> None:
        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None
        self.frame_no_map = frame_no_map

    def get_annotation_count(self, simple_annotation: dict[str, Any]) -> AnnotationCountByInputData:
        """
        1個のアノテーションJSONに対して、属性値ごとのアノテーション数を取得します。

        Args:
            simple_annotation: アノテーションJSONファイルの内容

        """

        def convert_attribute_value_to_type(value: bool | str | float | None) -> AttributeValueType:  # noqa: FBT001
            """
            アノテーションJSONに格納されている属性値を、dict用のkeyに変換する。

            Notes:
                アノテーションJSONに格納されている属性値の型はbool, str, floatの3つ

            """
            if value is None:
                return "empty"

            if isinstance(value, str) and value == "":
                return "empty"

            return "filled"

        details: list[dict[str, Any]] = simple_annotation["details"]

        annotation_count_by_attribute: dict[AttributeValueKey, int] = defaultdict(int)
        for detail in details:
            label = detail["label"]

            if self.target_labels is not None and label not in self.target_labels:
                continue

            if self.non_target_labels is not None and label in self.non_target_labels:
                continue

            for attribute_name, attribute_value in detail["attributes"].items():
                if self.target_attribute_names is not None and (label, attribute_name) not in self.target_attribute_names:
                    continue

                if self.non_target_attribute_names is not None and (label, attribute_name) in self.non_target_attribute_names:
                    continue

                attribute_key = (label, attribute_name, convert_attribute_value_to_type(attribute_value))
                annotation_count_by_attribute[attribute_key] += 1

        frame_no: int | None = None
        if self.frame_no_map is not None:
            frame_no = self.frame_no_map.get((simple_annotation["task_id"], simple_annotation["input_data_id"]))

        return AnnotationCountByInputData(
            project_id=simple_annotation["project_id"],
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            annotation_attribute_counts=annotation_count_by_attribute,
            frame_no=frame_no,
            updated_datetime=simple_annotation["updated_datetime"],
        )

    def get_annotation_count_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> list[AnnotationCountByInputData]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、属性値ごとのアノテーション数を取得する。

        """
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

            annotation_count = self.get_annotation_count(simple_annotation_dict)
            annotation_duration_list.append(annotation_count)

        return annotation_duration_list


class ListAnnotationCounterByTask:
    """値が入力されている属性の個数をタスク単位で順次集計します。"""

    def __init__(
        self,
        *,
        target_labels: Collection[str] | None = None,
        target_attribute_names: Collection[AttributeNameKey] | None = None,
    ) -> None:
        self.counter_by_input_data = ListAnnotationCounterByInputData(
            target_labels=target_labels,
            target_attribute_names=target_attribute_names,
        )

    def get_annotation_count(self, task_parser: SimpleAnnotationParserByTask) -> AnnotationCountByTask:
        """1タスクに含まれる属性の個数を集計します。

        Args:
            task_parser: タスク単位のアノテーションパーサー。

        Returns:
            タスク単位の集計結果。

        Raises:
            RuntimeError: タスクにアノテーションJSONが含まれない場合。
        """
        first_count: AnnotationCountByInputData | None = None
        input_data_count = 0
        annotation_attribute_counts: dict[AttributeValueKey, int] = defaultdict(int)
        for parser in task_parser.lazy_parse():
            count = self.counter_by_input_data.get_annotation_count(parser.load_json())
            if first_count is None:
                first_count = count
            input_data_count += 1
            for key, value in count.annotation_attribute_counts.items():
                annotation_attribute_counts[key] += value
        if first_count is None:
            raise RuntimeError(f"{task_parser.task_id} ディレクトリにはjsonファイルが1つも含まれていません。")
        return AnnotationCountByTask(
            project_id=first_count.project_id,
            task_id=first_count.task_id,
            task_status=first_count.task_status,
            task_phase=first_count.task_phase,
            task_phase_stage=first_count.task_phase_stage,
            input_data_count=input_data_count,
            annotation_attribute_counts=annotation_attribute_counts,
        )

    def iter_annotation_count(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> Iterator[AnnotationCountByTask]:
        """タスク単位の集計結果を順次返します。

        Args:
            annotation_path: アノテーションzipまたは展開したディレクトリ。
            target_task_ids: 集計対象のタスクID。
            task_query: 集計対象タスクの絞り込み条件。

        Yields:
            タスク単位の集計結果。
        """
        target_task_id_set = set(target_task_ids) if target_task_ids is not None else None
        for index, task_parser in enumerate(lazy_parse_simple_annotation_by_task(annotation_path)):
            if (index + 1) % 1000 == 0:
                logger.info(f"{index + 1} 件目のタスクを処理中")
            if target_task_id_set is not None and task_parser.task_id not in target_task_id_set:
                continue
            json_file_path_list = task_parser.json_file_path_list
            if not json_file_path_list:
                continue
            if task_query is not None:
                simple_annotation = task_parser.get_parser(json_file_path_list[0]).load_json()
                if not match_annotation_with_task_query(simple_annotation, task_query):
                    continue
            yield self.get_annotation_count(task_parser)


class AnnotationCountCsvByAttribute:
    """
    属性値ごとのアノテーション数をCSVに出力するためのクラス

    Args:
        selective_attribute_value_max_count: 選択肢系の属性の値の個数の上限。これを超えた場合は、非選択肢系属性（トラッキングIDやアノテーションリンクなど）とみなす

    """

    def __init__(self, selective_attribute_value_max_count: int = 20) -> None:
        self.selective_attribute_value_max_count = selective_attribute_value_max_count

    def _value_columns(self, annotation_count_list: Collection[HasAnnotationAttributeCounts], *, prior_attribute_columns: list[tuple[str, str, str]] | None) -> list[tuple[str, str, str]]:
        """
        CSVの数値列を取得します。
        """
        all_attr_key_set = {attr_key for c in annotation_count_list for attr_key in c.annotation_attribute_counts}
        if prior_attribute_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_attribute_columns))
            value_columns = prior_attribute_columns + remaining_columns

        else:
            value_columns = sorted(all_attr_key_set)

        # 重複している場合は、重複要素を取り除く。ただし元の順番は維持する
        value_columns = list(dict.fromkeys(value_columns).keys())
        return value_columns

    def get_columns_by_input_data(
        self,
        annotation_count_list: list[AnnotationCountByInputData],
        prior_attribute_columns: list[tuple[str, str, str]] | None = None,
    ) -> list[tuple[str, str, str]]:
        basic_columns = [
            ("project_id", "", ""),
            ("task_id", "", ""),
            ("task_status", "", ""),
            ("task_phase", "", ""),
            ("task_phase_stage", "", ""),
            ("input_data_id", "", ""),
            ("input_data_name", "", ""),
            ("frame_no", "", ""),
            ("updated_datetime", "", ""),
        ]
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns=prior_attribute_columns)
        return basic_columns + value_columns

    def get_columns_by_task(
        self,
        annotation_count_list: list[AnnotationCountByTask],
        prior_attribute_columns: list[tuple[str, str, str]] | None = None,
    ) -> list[tuple[str, str, str]]:
        basic_columns = [
            ("project_id", "", ""),
            ("task_id", "", ""),
            ("task_status", "", ""),
            ("task_phase", "", ""),
            ("task_phase_stage", "", ""),
            ("input_data_count", "", ""),
        ]
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns=prior_attribute_columns)
        return basic_columns + value_columns

    def create_df_by_input_data(
        self,
        annotation_count_list: list[AnnotationCountByInputData],
        *,
        prior_attribute_columns: list[tuple[str, str, str]] | None = None,
    ) -> pandas.DataFrame:
        def to_cell(c: AnnotationCountByInputData) -> dict[tuple[str, str, str], Any]:
            cell: dict[tuple[str, str, str], Any] = {
                ("project_id", "", ""): c.project_id,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("updated_datetime", "", ""): c.updated_datetime,
                ("frame_no", "", ""): c.frame_no,
            }
            cell.update(c.annotation_attribute_counts)  # type: ignore[arg-type]

            return cell

        columns = self.get_columns_by_input_data(annotation_count_list, prior_attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in annotation_count_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns=prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df

    def create_df_by_task(
        self,
        annotation_count_list: list[AnnotationCountByTask],
        *,
        prior_attribute_columns: list[tuple[str, str, str]] | None = None,
    ) -> pandas.DataFrame:
        def to_cell(c: AnnotationCountByTask) -> dict[tuple[str, str, str], Any]:
            cell: dict[tuple[str, str, str], Any] = {
                ("project_id", "", ""): c.project_id,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("input_data_count", "", ""): c.input_data_count,
            }
            cell.update(c.annotation_attribute_counts)  # type: ignore[arg-type]

            return cell

        columns = self.get_columns_by_task(annotation_count_list, prior_attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in annotation_count_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns=prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df


def get_frame_no_map(task_json_path: Path) -> dict[tuple[str, str], int]:
    with task_json_path.open(encoding="utf-8") as f:
        task_list = json.load(f)

    result = {}
    for task in task_list:
        task_id = task["task_id"]
        input_data_id_list = task["input_data_id_list"]
        for index, input_data_id in enumerate(input_data_id_list):
            # 画面に合わせて1始まりにする
            result[(task_id, input_data_id)] = index + 1
    return result


def get_attribute_columns(attribute_names: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    attribute_columns = [(label_name, attribute_name, value_type) for label_name, attribute_name in attribute_names for value_type in ["filled", "empty"]]
    return attribute_columns


class CountAnnotationAttributeFilledMain:
    @staticmethod
    def to_dict(count: AnnotationCountByInputData | AnnotationCountByTask, *, include_task_metadata: bool) -> dict[str, Any]:
        """集計結果をJSON出力用の辞書に変換する。

        Args:
            count: アノテーション数の集計結果。
            include_task_metadata: タスクメタデータを出力するかどうか。

        Returns:
            JSON出力用の辞書。
        """
        result = count.to_dict(encode_json=True)
        if not include_task_metadata:
            result.pop("task_metadata")
        return result

    def __init__(self, service: annofabapi.Resource, name_translator: AnnotationNameTranslator | None = None) -> None:
        self.service = service
        self.name_translator = name_translator

    def translate_count_names(self, count: AnnotationCountByInputData | AnnotationCountByTask) -> AnnotationCountByInputData | AnnotationCountByTask:
        """集計結果の名称を日本語名へ変換します。

        Args:
            count: 名称を変換する集計結果。

        Returns:
            名称を変換した集計結果。
        """
        if self.name_translator is None:
            return count
        translated_counts: dict[AttributeValueKey, int] = defaultdict(int)
        for (label_name, attribute_name, value_type), value in count.annotation_attribute_counts.items():
            translated_key: AttributeValueKey = (
                self.name_translator.label_name(label_name),
                self.name_translator.attribute_name(label_name, attribute_name),
                value_type,
            )
            translated_counts[translated_key] += value
        return replace(count, annotation_attribute_counts=translated_counts)

    def print_annotation_count_csv_by_input_data(
        self, annotation_count_list: list[AnnotationCountByInputData], output_file: Path, *, attribute_names: list[tuple[str, str]] | None, task_metadata_keys: Collection[str] | None = None
    ) -> None:
        attribute_columns: list[tuple[str, str, str]] | None = None
        if attribute_names is not None:
            attribute_columns = get_attribute_columns(attribute_names)
            if self.name_translator is not None:
                attribute_columns = [self.name_translator.attribute_value_key(e) for e in attribute_columns]

        df = AnnotationCountCsvByAttribute().create_df_by_input_data(annotation_count_list, prior_attribute_columns=attribute_columns)
        for key in task_metadata_keys or []:
            df.insert(2 + list(task_metadata_keys or []).index(key), (f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", ""), [count.task_metadata.get(key) for count in annotation_count_list])
        print_csv(df, output_file)

    def print_annotation_count_csv_by_task(
        self, annotation_count_list: list[AnnotationCountByTask], output_file: Path, *, attribute_names: list[tuple[str, str]] | None, task_metadata_keys: Collection[str] | None = None
    ) -> None:
        attribute_columns: list[tuple[str, str, str]] | None = None
        if attribute_names is not None:
            attribute_columns = get_attribute_columns(attribute_names)
            if self.name_translator is not None:
                attribute_columns = [self.name_translator.attribute_value_key(e) for e in attribute_columns]

        df = AnnotationCountCsvByAttribute().create_df_by_task(annotation_count_list, prior_attribute_columns=attribute_columns)
        for key in task_metadata_keys or []:
            df.insert(2 + list(task_metadata_keys or []).index(key), (f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", ""), [count.task_metadata.get(key) for count in annotation_count_list])
        print_csv(df, output_file)

    def print_annotation_count_summary(
        self,
        summaries: Collection[CountSummary],
        group_by: Collection[str],
        output_file: Path,
        output_format: OutputFormat,
        *,
        attribute_names: list[tuple[str, str]] | None,
    ) -> None:
        """属性入力数のサマリーを出力します。

        Args:
            summaries: サマリー集計結果。
            group_by: 集計キー。
            output_file: 出力先。
            output_format: 出力形式。
            attribute_names: 優先して出力する属性名。
        """
        attribute_columns = get_attribute_columns(attribute_names) if attribute_names is not None else []
        if self.name_translator is not None:
            attribute_columns = [self.name_translator.attribute_value_key(value) for value in attribute_columns]
        remaining_columns = sorted({cast(AttributeValueKey, key) for summary in summaries for key in summary.value_counts} - set(attribute_columns))
        attribute_columns = list(dict.fromkeys([*attribute_columns, *remaining_columns]))

        if output_format == OutputFormat.CSV:
            basic_columns = [(value, "", "") for value in [*group_by, "task_count", "input_data_count"]]
            columns = [*basic_columns, *attribute_columns]
            rows: list[dict[tuple[str, str, str], object]] = []
            for summary in summaries:
                row: dict[tuple[str, str, str], object] = {(key, "", ""): value for key, value in summary.group_values.items()}
                row[("task_count", "", "")] = summary.task_count
                row[("input_data_count", "", "")] = summary.input_data_count
                row.update(cast(dict[tuple[str, str, str], object], dict(summary.value_counts)))
                rows.append(row)
            df = pandas.DataFrame(rows, columns=pandas.MultiIndex.from_tuples(columns))
            df = df.fillna(dict.fromkeys(attribute_columns, 0))
            print_csv(df, output_file)
            return

        json_rows = [
            {
                **summary.group_values,
                "task_count": summary.task_count,
                "input_data_count": summary.input_data_count,
                "annotation_attribute_counts": encode_annotation_count_by_attribute(cast(dict[AttributeValueKey, int], summary.value_counts)),
            }
            for summary in summaries
        ]
        print_json(json_rows, is_pretty=output_format == OutputFormat.PRETTY_JSON, output=output_file)

    def print_annotation_count(  # noqa: PLR0912, PLR0913
        self,
        annotation_path: Path,
        output_file: Path,
        group_by: list[str],
        output_format: OutputFormat,
        *,
        task_metadata_keys: Collection[str] | None = None,
        task_metadata_by_task_id: dict[str, dict[str, Any]] | None = None,
        project_id: str | None = None,
        include_flag_attribute: bool = False,
        target_label_names: Collection[str] | None = None,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> None:
        annotation_specs: AnnotationSpecs | None = None
        target_attribute_names: list[AttributeNameKey] | None = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            if target_label_names is not None:
                target_label_names, not_found_names = annotation_specs.get_label_keys_by_label_names(target_label_names)
                if len(not_found_names) > 0:
                    logger.warning(f"指定されたラベル名のうち、アノテーション仕様に見つからなかったラベル名があります。 :: {not_found_names}")
            if not include_flag_attribute:
                target_attribute_names = annotation_specs.attribute_name_keys(excluded_attribute_types=[AdditionalDataDefinitionType.FLAG])
                if target_label_names is not None:
                    target_attribute_names = [e for e in target_attribute_names if e[0] in target_label_names]

        if is_summary_group(group_by):
            task_counts = (
                cast(AnnotationCountByTask, self.translate_count_names(count))
                for count in ListAnnotationCounterByTask(
                    target_labels=target_label_names,
                    target_attribute_names=target_attribute_names,
                ).iter_annotation_count(
                    annotation_path,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                )
            )
            summaries = aggregate_task_counts(
                task_counts,
                group_by,
                value_counts_getter=lambda count: count.annotation_attribute_counts,
                task_metadata_by_task_id=task_metadata_by_task_id,
            )
            logger.info(f"{sum(summary.task_count for summary in summaries)} 件のタスクを {len(summaries)} グループに集計しました。")
            self.print_annotation_count_summary(
                summaries,
                group_by,
                output_file,
                output_format,
                attribute_names=target_attribute_names,
            )
            return

        frame_no_map = get_frame_no_map(task_json_path) if task_json_path is not None else None

        annotation_count_list_by_input_data = ListAnnotationCounterByInputData(
            frame_no_map=frame_no_map,
            target_labels=target_label_names,
            target_attribute_names=target_attribute_names,
        ).get_annotation_count_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )
        if task_metadata_by_task_id is not None:
            annotation_count_list_by_input_data = [replace(count, task_metadata=task_metadata_by_task_id.get(count.task_id, {})) for count in annotation_count_list_by_input_data]
        annotation_count_list_by_input_data = [cast(AnnotationCountByInputData, self.translate_count_names(count)) for count in annotation_count_list_by_input_data]

        detail_group_by = GroupBy(group_by[0])
        if detail_group_by == GroupBy.INPUT_DATA_ID:
            logger.info(f"{len(annotation_count_list_by_input_data)} 件の入力データに含まれるアノテーション数の情報を出力します。")
            if output_format == OutputFormat.CSV:
                self.print_annotation_count_csv_by_input_data(
                    annotation_count_list_by_input_data,
                    output_file=output_file,
                    attribute_names=target_attribute_names,
                    task_metadata_keys=task_metadata_keys,
                )

            elif output_format in [OutputFormat.PRETTY_JSON, OutputFormat.JSON]:
                json_is_pretty = output_format == OutputFormat.PRETTY_JSON

                print_json(
                    [self.to_dict(count, include_task_metadata=bool(task_metadata_keys)) for count in annotation_count_list_by_input_data],
                    is_pretty=json_is_pretty,
                    output=output_file,
                )
        elif detail_group_by == GroupBy.TASK_ID:
            annotation_count_list_by_task = convert_annotation_count_list_by_input_data_to_by_task(annotation_count_list_by_input_data)
            logger.info(f"{len(annotation_count_list_by_task)} 件のタスクに含まれるアノテーション数の情報を出力します。")
            if output_format == OutputFormat.CSV:
                self.print_annotation_count_csv_by_task(annotation_count_list_by_task, output_file=output_file, attribute_names=target_attribute_names, task_metadata_keys=task_metadata_keys)

            elif output_format in [OutputFormat.PRETTY_JSON, OutputFormat.JSON]:
                json_is_pretty = output_format == OutputFormat.PRETTY_JSON

                print_json(
                    [self.to_dict(count, include_task_metadata=bool(task_metadata_keys)) for count in annotation_count_list_by_task],
                    is_pretty=json_is_pretty,
                    output=output_file,
                )

        else:
            assert_never(detail_group_by)


class CountAnnotationAttributeFilled(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip count_annotation_attribute_filled: error:"

    def validate(self, args: argparse.Namespace) -> bool:  # noqa: PLR0911
        group_by_error = validate_group_by(args.group_by)
        if group_by_error is not None:
            print(f"{self.COMMON_MESSAGE} {group_by_error}", file=sys.stderr)  # noqa: T201
            return False
        if args.with_task_metadata and is_summary_group(args.group_by):
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} `--with_task_metadata`は`--group_by task_id`または`--group_by input_data_id`を指定したときだけ使用できます。",
                file=sys.stderr,
            )
            return False
        if needs_task_metadata(args.group_by) and args.project_id is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: タスクメタデータで集計するときは、`--project_id`が必須です。",
                file=sys.stderr,
            )
            return False
        if args.use_japanese_name and args.project_id is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: `--use_japanese_name`を指定するときは、`--project_id`が必須です。",
                file=sys.stderr,
            )
            return False
        if args.with_task_metadata and args.project_id is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: `--with_task_metadata`を指定するときは、`--project_id`が必須です。",
                file=sys.stderr,
            )
            return False

        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        with_task_metadata: bool = args.with_task_metadata
        task_metadata_keys: list[str] = []
        task_metadata_by_task_id: dict[str, dict[str, Any]] | None = None
        if project_id is not None:
            super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        target_label_names = annofabcli.common.cli.get_list_from_args(args.label_name) if args.label_name is not None else None

        group_by: list[str] = args.group_by
        output_file: Path = args.output
        output_format = OutputFormat(args.format)
        name_translator = AnnotationNameTranslator.from_project(self.service, project_id) if args.use_japanese_name and project_id is not None else None
        main_obj = CountAnnotationAttributeFilledMain(self.service, name_translator)

        downloading_obj = DownloadingFile(self.service)

        def download_and_process_annotation(temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            # タスク全件ファイルは、フレーム番号またはタスクメタデータを参照するのに利用する
            if project_id is not None and (group_by == [INPUT_DATA_ID_GROUP] or with_task_metadata or needs_task_metadata(group_by)):
                # group_byで条件を絞り込んでいる理由：
                # タスクIDで集計する際は、フレーム番号は出力しないので、タスク全件ファイルをダウンロードする必要はないため
                task_json_path = downloading_obj.download_task_json_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )
            else:
                task_json_path = None

            if with_task_metadata or needs_task_metadata(group_by):
                assert task_json_path is not None
                task_metadata_by_task_id = get_task_metadata_by_task_id(task_json_path)
                task_metadata_keys = get_task_metadata_keys(task_metadata_by_task_id)
            else:
                task_metadata_by_task_id = None
                task_metadata_keys = []

            func = partial(
                main_obj.print_annotation_count,
                project_id=project_id,
                task_metadata_keys=task_metadata_keys,
                task_metadata_by_task_id=task_metadata_by_task_id,
                task_json_path=task_json_path,
                group_by=group_by,
                output_format=output_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                include_flag_attribute=args.include_flag_attribute,
                target_label_names=target_label_names,
            )

            if annotation_path is None:
                assert project_id is not None
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )
                func(annotation_path=annotation_path)
            else:
                func(annotation_path=annotation_path)

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_process_annotation(temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_process_annotation(temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            # プロジェクトIDが指定されていない場合は、アノテーションパスが必須なので、一時ディレクトリは不要
            assert annotation_path is not None
            func = partial(
                main_obj.print_annotation_count,
                project_id=project_id,
                task_metadata_keys=task_metadata_keys,
                task_metadata_by_task_id=task_metadata_by_task_id,
                task_json_path=None,
                group_by=group_by,
                output_format=output_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                include_flag_attribute=args.include_flag_attribute,
                target_label_names=target_label_names,
            )
            func(annotation_path=annotation_path)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CountAnnotationAttributeFilled(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        help="project_id。``--annotation`` が未指定のときは必須です。``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やCSV列順が決まります。",  # noqa: E501
    )

    parser.add_argument("--with_task_metadata", action="store_true", help="タスクメタデータを出力します。CSVでは ``task_metadata.<key>`` 列、JSONでは ``task_metadata`` キーに出力します。")

    parser.add_argument(
        "--group_by",
        type=str,
        nargs="+",
        default=[TASK_ID_GROUP],
        help="アノテーションの個数を集約する項目を指定します。指定できる値は task_id, input_data_id, project_id, task_phase, task_phase_stage, task_status, task_metadata.<key> です。"
        "サマリー項目は複数指定できます。",
    )

    parser.add_argument(
        "--include_flag_attribute",
        action="store_true",
        help="指定した場合は、On/Off属性（チェックボックス）も集計対象にします。"
        "On/Off属性は基本的に常に「入力されている」と判定されるため、デフォルトでは集計対象外にしています。"
        "``--project_id`` が指定されているときのみ有効なオプションです。",
    )

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        help="集計対象とするラベルの英語名を指定します。指定したラベルに属する属性のみが集計対象になります。 ``file://`` を先頭に付けると、ラベル名が記載されたファイルを指定できます。",
    )

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )

    argument_parser.add_output()

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="集計対象タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--latest",
        action="store_true",
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )
    add_use_japanese_name_argument(parser)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "count_annotation_attribute_filled"
    subcommand_help = "値が入力されている属性の個数を、タスクごとまたは入力データごとに集計します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
