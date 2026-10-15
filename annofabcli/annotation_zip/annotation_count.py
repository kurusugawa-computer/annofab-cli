# pylint: disable=too-many-lines
from __future__ import annotations

import abc
import collections
import copy
import json
import logging
import zipfile
from collections import Counter, defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import annofabapi
import pandas
from annofabapi.models import TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip,
    lazy_parse_simple_annotation_zip_by_task,
)
from annofabapi.pydantic_models.additional_data_definition_type import AdditionalDataDefinitionType
from dataclasses_json import DataClassJsonMixin, config

from annofabcli.annotation_zip.task_metadata import TASK_METADATA_COLUMN_PREFIX
from annofabcli.common.facade import (
    TaskQuery,
    convert_annotation_specs_labels_v2_to_v1,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv
from annofabcli.common.visualize import AddProps, MessageLocale

logger = logging.getLogger(__name__)


AttributeValueKey = tuple[str, str, str]
"""
属性のキー.
tuple[label_name_en, attribute_name_en, attribute_value] で表す。
"""

PER_INPUT_DATA_COLUMN_PREFIX = "per_input_data"
"""入力データあたりのアノテーション数を表す列名の接頭辞。"""

LabelKeys = Collection[str]

AttributeNameKey = tuple[str, str]
"""
属性名のキー.
tuple[label_name_en, attribute_name_en] で表す。
"""


AttributeKeys = Collection[Collection]


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


def encode_annotation_count_by_attribute(
    annotation_count_by_attribute: Counter[AttributeValueKey],
) -> dict[str, dict[str, dict[str, int]]]:
    """annotation_count_by_attributeを `{label_name: {attribute_name: {attribute_value: annotation_count}}}`のdictに変換します。
    JSONへの変換用関数です。
    """

    def _factory():  # noqa: ANN202
        """入れ子の辞書を利用できるようにするための関数"""
        return collections.defaultdict(_factory)

    result: dict[str, dict[str, dict[str, int]]] = defaultdict(_factory)
    for (label_name, attribute_name, attribute_value), annotation_count in annotation_count_by_attribute.items():
        result[label_name][attribute_name][attribute_value] = annotation_count
    return result


@dataclass(frozen=True)
class AnnotationCounter(abc.ABC):
    """
    アノテーションの集計情報を保持する抽象基底クラス。

    Attributes:
        annotation_count: アノテーションの総数
        annotation_count_by_label: ラベルごとのアノテーション数
        annotation_count_by_attribute: 属性値ごとのアノテーション数
    """

    annotation_count: int
    annotation_count_by_label: Counter[str]
    annotation_count_by_attribute: Counter[AttributeValueKey] = field(
        metadata=config(
            encoder=encode_annotation_count_by_attribute,
        )
    )


@dataclass(frozen=True)
class AnnotationCounterByTask(AnnotationCounter, DataClassJsonMixin):
    """
    タスク単位でのアノテーション集計情報。

    Attributes:
        project_id: プロジェクトID
        task_id: タスクID
        task_status: タスクのステータス
        task_phase: タスクのフェーズ
        task_phase_stage: タスクフェーズのステージ番号
        input_data_count: タスクに含まれる入力データの数
    """

    project_id: str
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    input_data_count: int
    task_metadata: dict[str, Any] = field(default_factory=dict)
    """出力対象とするタスクメタデータ。"""


@dataclass(frozen=True)
class AnnotationCounterByInputData(AnnotationCounter, DataClassJsonMixin):
    """
    入力データ単位でのアノテーション集計情報。

    Attributes:
        project_id: プロジェクトID
        task_id: タスクID
        task_status: タスクのステータス
        task_phase: タスクのフェーズ
        task_phase_stage: タスクフェーズのステージ番号
        input_data_id: 入力データID
        input_data_name: 入力データ名
        updated_datetime: アノテーションJSONに格納されているアノテーションの更新日時
        frame_no: フレーム番号。アノテーションJSONには含まれていない情報なので、Optionalにする
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
    frame_no: int | None = None
    """アノテーションJSONには含まれていない情報なので、Optionalにする"""
    task_metadata: dict[str, Any] = field(default_factory=dict)
    """出力対象とするタスクメタデータ。"""


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    """
    アノテーションzipまたはディレクトリから、入力データ単位でアノテーションを遅延パースするイテレータを返します。

    Args:
        annotation_path: アノテーションzipまたはzipを展開したディレクトリのパス

    Returns:
        SimpleAnnotationParserのイテレータ

    Raises:
        RuntimeError: 指定されたパスが存在しない場合、またはzipファイルでもディレクトリでもない場合
    """
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


def lazy_parse_simple_annotation_by_task(annotation_path: Path) -> Iterator[SimpleAnnotationParserByTask]:
    """
    アノテーションzipまたはディレクトリから、タスク単位でアノテーションを遅延パースするイテレータを返します。

    Args:
        annotation_path: アノテーションzipまたはzipを展開したディレクトリのパス

    Returns:
        SimpleAnnotationParserByTaskのイテレータ

    Raises:
        RuntimeError: 指定されたパスが存在しない場合、またはzipファイルでもディレクトリでもない場合
    """
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir_by_task(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip_by_task(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


class ListAnnotationCounterByInputData:
    """入力データ単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。

    Args:
        target_labels: 集計対象のラベル（label_name_en）。`non_target_labels`との同時指定不可。
        target_attribute_names: 集計対象の属性名。`non_target_attribute_names`との同時指定不可。
        non_target_labels: 集計対象外のラベル。`target_labels`との同時指定不可。
        non_target_attribute_names: 集計対象外の属性名のキー。`target_attribute_names`との同時指定不可。
        target_attribute_names_only: 集計対象の属性名（属性名のみでフィルタリング）。ラベル名に関係なく、指定された属性名のみが対象になります。
        frame_no_map: key:task_id,input_data_idのtuple, value:フレーム番号

    Raises:
        ValueError: `target_labels`と`non_target_labels`の両方が指定された場合、
            または`target_attribute_names`と`non_target_attribute_names`の両方が指定された場合に発生します。

    """

    def __init__(
        self,
        *,
        target_labels: Collection[str] | None = None,
        non_target_labels: Collection[str] | None = None,
        target_attribute_names: Collection[AttributeNameKey] | None = None,
        non_target_attribute_names: Collection[AttributeNameKey] | None = None,
        target_attribute_names_only: Collection[str] | None = None,
        frame_no_map: dict[tuple[str, str], int] | None = None,
    ) -> None:
        if target_labels is not None and non_target_labels is not None:
            raise ValueError("`target_labels`と`non_target_labels`の両方が指定されています。")
        if target_attribute_names is not None and non_target_attribute_names is not None:
            raise ValueError("`target_attribute_names`と`non_target_attribute_names`の両方が指定されています。")

        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None
        self.target_attribute_names_only = set(target_attribute_names_only) if target_attribute_names_only is not None else None
        self.frame_no_map = frame_no_map

    def get_annotation_counter(
        self,
        simple_annotation: dict[str, Any],
    ) -> AnnotationCounterByInputData:
        """
        1個の入力データに対して、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
        """

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

        details = simple_annotation["details"]

        annotation_count_by_label = collections.Counter([e["label"] for e in details])
        if self.target_labels is not None:
            annotation_count_by_label = collections.Counter({label: count for label, count in annotation_count_by_label.items() if label in self.target_labels})
        if self.non_target_labels is not None:
            annotation_count_by_label = collections.Counter({label: count for label, count in annotation_count_by_label.items() if label not in self.non_target_labels})

        attributes_list: list[AttributeValueKey] = []
        for detail in details:
            label = detail["label"]
            for attribute, value in detail["attributes"].items():
                attributes_list.append((label, attribute, convert_attribute_value_to_key(value)))

        annotation_count_by_attribute = collections.Counter(attributes_list)
        if self.target_labels is not None:
            annotation_count_by_attribute = collections.Counter(
                {(label, attribute_name, attribute_value): count for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items() if label in self.target_labels}
            )
        if self.non_target_labels is not None:
            annotation_count_by_attribute = collections.Counter(
                {(label, attribute_name, attribute_value): count for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items() if label not in self.non_target_labels}
            )
        if self.target_attribute_names is not None:
            annotation_count_by_attribute = collections.Counter(
                {
                    (label, attribute_name, attribute_value): count
                    for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items()
                    if (label, attribute_name) in self.target_attribute_names
                }
            )
        if self.target_attribute_names_only is not None:
            annotation_count_by_attribute = collections.Counter(
                {
                    (label, attribute_name, attribute_value): count
                    for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items()
                    if attribute_name in self.target_attribute_names_only
                }
            )
        if self.non_target_attribute_names is not None:
            annotation_count_by_attribute = collections.Counter(
                {
                    (label, attribute_name, attribute_value): count
                    for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items()
                    if (label, attribute_name) not in self.non_target_attribute_names
                }
            )

        task_id = simple_annotation["task_id"]
        input_data_id = simple_annotation["input_data_id"]
        frame_no: int | None = None
        if self.frame_no_map is not None:
            frame_no = self.frame_no_map.get((task_id, input_data_id))

        return AnnotationCounterByInputData(
            project_id=simple_annotation["project_id"],
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            updated_datetime=simple_annotation["updated_datetime"],
            annotation_count=sum(annotation_count_by_label.values()),
            annotation_count_by_label=annotation_count_by_label,
            annotation_count_by_attribute=annotation_count_by_attribute,
            frame_no=frame_no,
        )

    def get_annotation_counter_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> list[AnnotationCounterByInputData]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        """

        counter_list = []

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

            input_data_counter = self.get_annotation_counter(simple_annotation_dict)
            counter_list.append(input_data_counter)

        return counter_list


class ListAnnotationCounterByTask:
    """タスク単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。

    Args:
        target_labels: 集計対象のラベル（label_name_en）。`non_target_labels`との同時指定不可。
        target_attribute_names: 集計対象の属性名。`non_target_attribute_names`との同時指定不可。
        non_target_labels: 集計対象外のラベル。`target_labels`との同時指定不可。
        non_target_attribute_names: 集計対象外の属性名のキー。`target_attribute_names`との同時指定不可。
        target_attribute_names_only: 集計対象の属性名（属性名のみでフィルタリング）。ラベル名に関係なく、指定された属性名のみが対象になります。

    Raises:
        ValueError: `target_labels`と`non_target_labels`の両方が指定された場合、
            または`target_attribute_names`と`non_target_attribute_names`の両方が指定された場合に発生します。

    """

    def __init__(
        self,
        *,
        target_labels: Collection[str] | None = None,
        non_target_labels: Collection[str] | None = None,
        target_attribute_names: Collection[AttributeNameKey] | None = None,
        non_target_attribute_names: Collection[AttributeNameKey] | None = None,
        target_attribute_names_only: Collection[str] | None = None,
    ) -> None:
        if target_labels is not None and non_target_labels is not None:
            raise ValueError("`target_labels`と`non_target_labels`の両方が指定されています。")
        if target_attribute_names is not None and non_target_attribute_names is not None:
            raise ValueError("`target_attribute_names`と`non_target_attribute_names`の両方が指定されています。")

        self.counter_by_input_data = ListAnnotationCounterByInputData(
            target_labels=target_labels,
            non_target_labels=non_target_labels,
            target_attribute_names=target_attribute_names,
            non_target_attribute_names=non_target_attribute_names,
            target_attribute_names_only=target_attribute_names_only,
        )

    def get_annotation_counter(self, task_parser: SimpleAnnotationParserByTask) -> AnnotationCounterByTask:
        """
        1個のタスクに対して、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
            target_labels: 集計対象のラベル（label_name_en）
            target_attributes: 集計対象の属性


        """

        annotation_count_by_label: Counter[str] = collections.Counter()
        annotation_count_by_attribute: Counter[tuple[str, str, str]] = collections.Counter()

        last_simple_annotation = None
        input_data_count = 0
        for parser in task_parser.lazy_parse():
            # parse()メソッドは遅いので、使わない
            simple_annotation_dict = parser.load_json()
            input_data = self.counter_by_input_data.get_annotation_counter(simple_annotation_dict)
            annotation_count_by_label += input_data.annotation_count_by_label
            annotation_count_by_attribute += input_data.annotation_count_by_attribute
            last_simple_annotation = simple_annotation_dict
            input_data_count += 1

        if last_simple_annotation is None:
            raise RuntimeError(f"{task_parser.task_id} ディレクトリにはjsonファイルが1つも含まれていません。")

        return AnnotationCounterByTask(
            project_id=last_simple_annotation["project_id"],
            task_id=last_simple_annotation["task_id"],
            task_status=TaskStatus(last_simple_annotation["task_status"]),
            task_phase=TaskPhase(last_simple_annotation["task_phase"]),
            task_phase_stage=last_simple_annotation["task_phase_stage"],
            input_data_count=input_data_count,
            annotation_count=sum(annotation_count_by_label.values()),
            annotation_count_by_label=annotation_count_by_label,
            annotation_count_by_attribute=annotation_count_by_attribute,
        )

    def get_annotation_counter_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> list[AnnotationCounterByTask]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        """

        return list(
            self.iter_annotation_counter(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )
        )

    def iter_annotation_counter(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> Iterator[AnnotationCounterByTask]:
        """アノテーション数のタスク単位集計結果を順次返します。

        Args:
            annotation_path: アノテーションzipまたは展開したディレクトリ。
            target_task_ids: 集計対象のタスクID。
            task_query: 集計対象タスクの絞り込み条件。

        Yields:
            タスク単位の集計結果。
        """
        iter_task_parser = lazy_parse_simple_annotation_by_task(annotation_path)

        target_task_ids = set(target_task_ids) if target_task_ids is not None else None

        logger.debug("アノテーションzip/ディレクトリを読み込み中")
        for task_index, task_parser in enumerate(iter_task_parser):
            if (task_index + 1) % 1000 == 0:
                logger.info(f"{task_index + 1} 件目のタスクを処理中")

            if target_task_ids is not None and task_parser.task_id not in target_task_ids:
                continue

            if task_query is not None:
                json_file_path_list = task_parser.json_file_path_list
                if len(json_file_path_list) == 0:
                    continue

                input_data_parser = task_parser.get_parser(json_file_path_list[0])
                dict_simple_annotation = input_data_parser.load_json()
                if not match_annotation_with_task_query(dict_simple_annotation, task_query):
                    continue

            yield self.get_annotation_counter(task_parser)


class AttributeCountCsv:
    """
    属性値ごとのアノテーション数を記載するCSV。
    """

    def _value_columns(
        self,
        counter_list: Collection[AnnotationCounter],
        prior_attribute_columns: list[AttributeValueKey] | None,
    ) -> list[AttributeValueKey]:
        """
        CSV出力のための属性値列の順序を決定します。

        Args:
            counter_list: アノテーション集計情報のコレクション
            prior_attribute_columns: 優先的に配置する属性値のキーのリスト。Noneの場合はソート順で配置されます。

        Returns:
            属性値のキーのリスト（CSV列の順序）
        """
        all_attr_key_set = {attr_key for c in counter_list for attr_key in c.annotation_count_by_attribute}
        if prior_attribute_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_attribute_columns))

            # `remaining_columns`には、属性値が空である列などが格納されている
            # `remaining_columns`を、`value_columns`の関連している位置に挿入する。
            value_columns = copy.deepcopy(prior_attribute_columns)
            for remaining_column in remaining_columns:
                is_inserted = False
                for i in range(len(value_columns) - 1, -1, -1):
                    col = value_columns[i]
                    if col[0:2] == remaining_column[0:2]:
                        value_columns.insert(i + 1, remaining_column)
                        is_inserted = True
                        break
                if not is_inserted:
                    value_columns.append(remaining_column)

            assert len(value_columns) == len(prior_attribute_columns) + len(remaining_columns)

        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = remaining_columns

        # 重複している場合は、重複要素を取り除く。ただし元の順番は維持する
        value_columns = list(dict.fromkeys(value_columns).keys())
        return value_columns

    @staticmethod
    def _per_input_data_column(column: AttributeValueKey) -> AttributeValueKey:
        return (f"{PER_INPUT_DATA_COLUMN_PREFIX}.{column[0]}", column[1], column[2])

    def _per_input_data_columns(self, value_columns: list[AttributeValueKey], *, with_annotation_count: bool) -> list[AttributeValueKey]:
        columns = [self._per_input_data_column(e) for e in value_columns]
        if with_annotation_count:
            return [(f"{PER_INPUT_DATA_COLUMN_PREFIX}.annotation_count", "", ""), *columns]
        return columns

    @staticmethod
    def _per_input_data_value(annotation_count: int, input_data_count: int) -> float:
        if input_data_count == 0:
            return 0.0
        return annotation_count / input_data_count

    def print_csv_by_task(
        self,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        prior_attribute_columns: list[AttributeValueKey] | None = None,
        with_per_input_data: bool = False,  # noqa: FBT001, FBT002
        with_annotation_count: bool = True,  # noqa: FBT001, FBT002
        task_metadata_keys: Collection[str] | None = None,
    ) -> None:
        """
        タスク単位の属性値ごとアノテーション数をCSVファイルに出力します。

        Args:
            counter_list: タスク単位のアノテーション集計情報のリスト
            output_file: 出力先CSVファイルのパス
            prior_attribute_columns: 優先的に配置する属性値のキーのリスト
            with_per_input_data: 入力データあたりの属性値ごとのアノテーション数を出力するかどうか
            with_annotation_count: アノテーション総数を出力するかどうか
        """

        def get_columns() -> list[AttributeValueKey]:
            basic_columns: list[AttributeValueKey] = [
                ("project_id", "", ""),
                ("task_id", "", ""),
                *[(f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", "") for key in task_metadata_keys or []],
                ("task_phase", "", ""),
                ("task_phase_stage", "", ""),
                ("task_status", "", ""),
                ("input_data_count", "", ""),
            ]
            if with_annotation_count:
                basic_columns.append(("annotation_count", "", ""))
            value_columns = self._value_columns(counter_list, prior_attribute_columns)
            per_input_data_columns = self._per_input_data_columns(value_columns, with_annotation_count=with_annotation_count) if with_per_input_data else []
            return basic_columns + value_columns + per_input_data_columns

        def to_cell(c: AnnotationCounterByTask) -> dict[AttributeValueKey, Any]:
            cell: dict[AttributeValueKey, Any] = {
                ("project_id", "", ""): c.project_id,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("input_data_count", "", ""): c.input_data_count,
            }
            cell.update({(f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", ""): c.task_metadata.get(key) for key in task_metadata_keys or []})
            if with_annotation_count:
                cell[("annotation_count", "", "")] = c.annotation_count
            cell.update(c.annotation_count_by_attribute)
            if with_per_input_data:
                if with_annotation_count:
                    cell[(f"{PER_INPUT_DATA_COLUMN_PREFIX}.annotation_count", "", "")] = self._per_input_data_value(c.annotation_count, c.input_data_count)
                cell.update({self._per_input_data_column(k): self._per_input_data_value(v, c.input_data_count) for k, v in c.annotation_count_by_attribute.items()})
            return cell

        columns = get_columns()
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数を表す列の欠損値だけを0に変換する。
        # タスクメタデータの欠損値は、CSVでは空欄として出力する。
        value_columns = self._value_columns(counter_list, prior_attribute_columns)
        per_input_data_columns = self._per_input_data_columns(value_columns, with_annotation_count=with_annotation_count) if with_per_input_data else []
        df = df.fillna(dict.fromkeys(value_columns + per_input_data_columns, 0))

        print_csv(df, output=output_file)

    def print_csv_by_input_data(
        self,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        prior_attribute_columns: list[AttributeValueKey] | None = None,
        with_annotation_count: bool = True,  # noqa: FBT001, FBT002
        task_metadata_keys: Collection[str] | None = None,
    ) -> None:
        """
        入力データ単位の属性値ごとアノテーション数をCSVファイルに出力します。

        Args:
            counter_list: 入力データ単位のアノテーション集計情報のリスト
            output_file: 出力先CSVファイルのパス
            prior_attribute_columns: 優先的に配置する属性値のキーのリスト
            with_annotation_count: アノテーション総数を出力するかどうか
        """

        def get_columns() -> list[AttributeValueKey]:
            basic_columns: list[AttributeValueKey] = [
                ("project_id", "", ""),
                ("task_id", "", ""),
                *[(f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", "") for key in task_metadata_keys or []],
                ("task_phase", "", ""),
                ("task_phase_stage", "", ""),
                ("task_status", "", ""),
                ("input_data_id", "", ""),
                ("input_data_name", "", ""),
                ("frame_no", "", ""),
                ("updated_datetime", "", ""),
            ]
            if with_annotation_count:
                basic_columns.append(("annotation_count", "", ""))
            value_columns = self._value_columns(counter_list, prior_attribute_columns)
            return basic_columns + value_columns

        def to_cell(c: AnnotationCounterByInputData) -> dict[tuple[str, str, str], Any]:
            cell = {
                ("project_id", "", ""): c.project_id,
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("frame_no", "", ""): c.frame_no,
                ("updated_datetime", "", ""): c.updated_datetime,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
            }
            cell.update({(f"{TASK_METADATA_COLUMN_PREFIX}.{key}", "", ""): c.task_metadata.get(key) for key in task_metadata_keys or []})
            if with_annotation_count:
                cell[("annotation_count", "", "")] = c.annotation_count
            cell.update(c.annotation_count_by_attribute)

            return cell

        columns = get_columns()
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(counter_list, prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))

        print_csv(df, output=output_file)


class LabelCountCsv:
    """
    ラベルごとのアノテーション数を記載するCSV。


    """

    def _value_columns(self, counter_list: Collection[AnnotationCounter], prior_label_columns: list[str] | None) -> list[str]:
        """
        CSV出力のためのラベル列の順序を決定します。

        Args:
            counter_list: アノテーション集計情報のコレクション
            prior_label_columns: 優先的に配置するラベル名のリスト。Noneの場合はソート順で配置されます。

        Returns:
            ラベル名のリスト（CSV列の順序）
        """
        all_attr_key_set = {attr_key for c in counter_list for attr_key in c.annotation_count_by_label}
        if prior_label_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_label_columns))
            value_columns = prior_label_columns + remaining_columns
        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = remaining_columns

        return value_columns

    @staticmethod
    def _per_input_data_column(column: str) -> str:
        return f"{PER_INPUT_DATA_COLUMN_PREFIX}.{column}"

    def _per_input_data_columns(self, value_columns: list[str], *, with_annotation_count: bool) -> list[str]:
        columns = [self._per_input_data_column(e) for e in value_columns]
        if with_annotation_count:
            return [self._per_input_data_column("annotation_count"), *columns]
        return columns

    @staticmethod
    def _per_input_data_value(annotation_count: int, input_data_count: int) -> float:
        if input_data_count == 0:
            return 0.0
        return annotation_count / input_data_count

    def print_csv_by_task(
        self,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        prior_label_columns: list[str] | None = None,
        with_per_input_data: bool = False,  # noqa: FBT001, FBT002
        with_annotation_count: bool = True,  # noqa: FBT001, FBT002
        task_metadata_keys: Collection[str] | None = None,
    ) -> None:
        """
        タスク単位のラベルごとアノテーション数をCSVファイルに出力します。

        Args:
            counter_list: タスク単位のアノテーション集計情報のリスト
            output_file: 出力先CSVファイルのパス
            prior_label_columns: 優先的に配置するラベル名のリスト
            with_per_input_data: 入力データあたりのラベルごとのアノテーション数を出力するかどうか
            with_annotation_count: アノテーション総数を出力するかどうか
        """

        def get_columns() -> list[str]:
            basic_columns = [
                "project_id",
                "task_id",
                *[f"{TASK_METADATA_COLUMN_PREFIX}.{key}" for key in task_metadata_keys or []],
                "task_phase",
                "task_phase_stage",
                "task_status",
                "input_data_count",
            ]
            if with_annotation_count:
                basic_columns.append("annotation_count")
            value_columns = self._value_columns(counter_list, prior_label_columns)
            per_input_data_columns = self._per_input_data_columns(value_columns, with_annotation_count=with_annotation_count) if with_per_input_data else []
            return basic_columns + value_columns + per_input_data_columns

        def to_dict(c: AnnotationCounterByTask) -> dict[str, Any]:
            d: dict[str, Any] = {
                "project_id": c.project_id,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "input_data_count": c.input_data_count,
            }
            d.update({f"{TASK_METADATA_COLUMN_PREFIX}.{key}": c.task_metadata.get(key) for key in task_metadata_keys or []})
            if with_annotation_count:
                d["annotation_count"] = c.annotation_count
            # キーをラベル名、値をラベルごとのアノテーション数にしたdictに変換する
            d.update(c.annotation_count_by_label)
            if with_per_input_data:
                if with_annotation_count:
                    d[self._per_input_data_column("annotation_count")] = self._per_input_data_value(c.annotation_count, c.input_data_count)
                d.update({self._per_input_data_column(k): self._per_input_data_value(v, c.input_data_count) for k, v in c.annotation_count_by_label.items()})
            return d

        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=get_columns())

        # アノテーション数を表す列の欠損値だけを0に変換する。
        # タスクメタデータの欠損値は、CSVでは空欄として出力する。
        value_columns = self._value_columns(counter_list, prior_label_columns)
        per_input_data_columns = self._per_input_data_columns(value_columns, with_annotation_count=with_annotation_count) if with_per_input_data else []
        df = df.fillna(dict.fromkeys(value_columns + per_input_data_columns, 0))
        print_csv(df, output=output_file)

    def print_csv_by_input_data(
        self,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        prior_label_columns: list[str] | None = None,
        with_annotation_count: bool = True,  # noqa: FBT001, FBT002
        task_metadata_keys: Collection[str] | None = None,
    ) -> None:
        """
        入力データ単位のラベルごとアノテーション数をCSVファイルに出力します。

        Args:
            counter_list: 入力データ単位のアノテーション集計情報のリスト
            output_file: 出力先CSVファイルのパス
            prior_label_columns: 優先的に配置するラベル名のリスト
            with_annotation_count: アノテーション総数を出力するかどうか
        """

        def get_columns() -> list[str]:
            basic_columns = [
                "project_id",
                "task_id",
                *[f"{TASK_METADATA_COLUMN_PREFIX}.{key}" for key in task_metadata_keys or []],
                "task_phase",
                "task_phase_stage",
                "task_status",
                "input_data_id",
                "input_data_name",
                "frame_no",
                "updated_datetime",
            ]
            if with_annotation_count:
                basic_columns.append("annotation_count")
            value_columns = self._value_columns(counter_list, prior_label_columns)
            return basic_columns + value_columns

        def to_dict(c: AnnotationCounterByInputData) -> dict[str, Any]:
            d = {
                "project_id": c.project_id,
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "frame_no": c.frame_no,
                "updated_datetime": c.updated_datetime,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
            }
            d.update({f"{TASK_METADATA_COLUMN_PREFIX}.{key}": c.task_metadata.get(key) for key in task_metadata_keys or []})
            if with_annotation_count:
                d["annotation_count"] = c.annotation_count
            d.update(c.annotation_count_by_label)
            return d

        columns = get_columns()
        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=columns)

        # アノテーション数列のNaNを0に変換する
        value_columns = self._value_columns(counter_list, prior_label_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))

        print_csv(df, output=output_file)


class AnnotationSpecs:
    """

    Args:
        annotation_type: 出力対象のラベルの種類。

    """

    def __init__(self, service: annofabapi.Resource, project_id: str, *, annotation_type: str | None = None) -> None:
        self.service = service
        self.project_id = project_id

        annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        self._annotation_specs = annotation_specs

        labels_v2 = annotation_specs["labels"]
        if annotation_type is not None:
            labels_v2 = [e for e in labels_v2 if e["annotation_type"] == annotation_type]

        self._labels_v1 = convert_annotation_specs_labels_v2_to_v1(labels_v2=labels_v2, additionals_v2=annotation_specs["additionals"])

    def label_keys(self) -> list[str]:
        """ラベル名（英語名）のキーの一覧"""

        def to_label_name(label: dict[str, Any]) -> str:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""
            return label_name_en

        result = [to_label_name(label) for label in self._labels_v1]
        duplicated_labels = [key for key, value in collections.Counter(result).items() if value > 1]
        if len(duplicated_labels) > 0:
            logger.warning(f"アノテーション仕様のラベル英語名が重複しています。アノテーション個数が正しく算出できない可能性があります。:: {duplicated_labels}")
        return result

    def get_label_keys_by_label_names(self, label_names: Collection[str]) -> tuple[list[str], list[str]]:
        """指定されたラベル名のうち、アノテーション仕様に存在するラベル名と存在しないラベル名を返します。"""
        label_names_set = set(label_names)
        label_keys = self.label_keys()
        return [e for e in label_keys if e in label_names_set], list(label_names_set - set(label_keys))

    def attribute_name_keys(
        self,
        excluded_attribute_types: Collection[AdditionalDataDefinitionType] | None = None,
        include_attribute_types: Collection[AdditionalDataDefinitionType] | None = None,
    ) -> list[tuple[str, str]]:
        """
        属性名の一覧を取得します。

        Args:
            include_attribute_types: 指定した属性の種類に合致した属性名の一覧を取得します。
            excluded_attribute_types: 指定した属性の種類に合致していない属性名の一覧を取得します。

        Raise:
            ValueError: `include_attribute_types`と`excluded_attribute_types`の両方が指定された場合に発生します。
        """
        if excluded_attribute_types is not None and include_attribute_types is not None:
            raise ValueError("`include_attribute_types`と`excluded_attribute_types`の両方が指定されています。")

        result = []
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            assert label_name_en is not None

            for attribute in label["additional_data_definitions"]:
                if excluded_attribute_types is not None and AdditionalDataDefinitionType(attribute["type"]) in excluded_attribute_types:
                    continue

                if include_attribute_types is not None and AdditionalDataDefinitionType(attribute["type"]) not in include_attribute_types:
                    continue

                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                assert attribute_name_en is not None
                result.append((label_name_en, attribute_name_en))

        duplicated_attribute_names = [key for key, value in collections.Counter(result).items() if value > 1]
        if len(duplicated_attribute_names) > 0:
            logger.warning(f"アノテーション仕様の属性情報（ラベル英語名、属性英語名）が重複しています。アノテーション個数が正しく算出できない可能性があります。:: {duplicated_attribute_names}")

        return result

    def get_attribute_value_keys_for_target_attributes(self, target_attribute_names: Collection[AttributeNameKey]) -> list[AttributeValueKey]:
        """
        指定された属性名のキーに対応する属性値のキーの一覧を取得します。

        Args:
            target_attribute_names: 属性値のキーを取得する対象の属性名のキー。
        """
        target_attribute_value_keys = []
        target_attribute_names_set = set(target_attribute_names)
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""

            for attribute in label["additional_data_definitions"]:
                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                attribute_name_en = attribute_name_en if attribute_name_en is not None else ""

                if (label_name_en, attribute_name_en) not in target_attribute_names_set:
                    continue

                attribute_type = AdditionalDataDefinitionType(attribute["type"])
                if attribute_type in [AdditionalDataDefinitionType.CHOICE, AdditionalDataDefinitionType.SELECT]:
                    for choice in attribute["choices"]:
                        choice_name_en = AddProps.get_message(choice["name"], MessageLocale.EN)
                        choice_name_en = choice_name_en if choice_name_en is not None else ""
                        target_attribute_value_keys.append((label_name_en, attribute_name_en, choice_name_en))

                elif attribute_type == AdditionalDataDefinitionType.FLAG:
                    target_attribute_value_keys.extend([(label_name_en, attribute_name_en, "true"), (label_name_en, attribute_name_en, "false")])

        return target_attribute_value_keys

    def selective_attribute_value_keys(self) -> list[AttributeValueKey]:
        """
        選択系（ドロップダウン／ラジオボタン／チェックボックス／フラグ）の属性の属性値のキーの一覧。

        対象となる属性種類:
        * ドロップダウン
        * ラジオボタン
        * チェックボックス
        * フラグ
        """
        selective_attribute_names = self.selective_attribute_name_keys()
        target_attribute_value_keys = self.get_attribute_value_keys_for_target_attributes(selective_attribute_names)

        duplicated_attributes = [key for key, value in collections.Counter(target_attribute_value_keys).items() if value > 1]
        if len(duplicated_attributes) > 0:
            logger.warning(
                f"アノテーション仕様の属性情報（ラベル英語名、属性英語名、選択肢英語名）が重複しています。アノテーション個数が正しく算出できない可能性があります。:: {duplicated_attributes}"
            )

        return target_attribute_value_keys

    def selective_attribute_name_keys(self) -> list[AttributeNameKey]:
        """
        選択系の属性の名前のキーの一覧
        * ドロップダウン
        * ラジオボタン
        * チェックボックス
        """
        target_attributes_columns = []
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""

            for attribute in label["additional_data_definitions"]:
                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                attribute_name_en = attribute_name_en if attribute_name_en is not None else ""

                if AdditionalDataDefinitionType(attribute["type"]) in [
                    AdditionalDataDefinitionType.CHOICE,
                    AdditionalDataDefinitionType.SELECT,
                    AdditionalDataDefinitionType.FLAG,
                ]:
                    target_attributes_columns.append((label_name_en, attribute_name_en))

        return target_attributes_columns

    def get_attribute_name_keys_by_attribute_names(self, attribute_names: Collection[str]) -> tuple[list[AttributeNameKey], list[str]]:
        """
        指定された属性名を持つ全てのラベルと属性の組み合わせを取得します。

        Args:
            attribute_names: 検索対象の属性名のリスト

        Returns:
            (見つかった属性名キーのリスト, 見つからなかった属性名のリスト) のタプル
        """
        attribute_names_set = set(attribute_names)
        result = []
        found_attribute_names = set()
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""

            for attribute in label["additional_data_definitions"]:
                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                attribute_name_en = attribute_name_en if attribute_name_en is not None else ""

                if attribute_name_en in attribute_names_set:
                    result.append((label_name_en, attribute_name_en))
                    found_attribute_names.add(attribute_name_en)

        not_found_attribute_names = list(attribute_names_set - found_attribute_names)
        return result, not_found_attribute_names

    def non_selective_attribute_name_keys(self) -> list[AttributeNameKey]:
        """
        非選択系の属性の名前のキー
        * トラッキングID
        * 数値
        * テキスト
        * アノテーションリンク


        """
        target_attributes_columns = []
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""

            for attribute in label["additional_data_definitions"]:
                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                attribute_name_en = attribute_name_en if attribute_name_en is not None else ""

                if AdditionalDataDefinitionType(attribute["type"]) in [
                    AdditionalDataDefinitionType.INTEGER,
                    AdditionalDataDefinitionType.TEXT,
                    AdditionalDataDefinitionType.COMMENT,
                    AdditionalDataDefinitionType.TRACKING,
                    AdditionalDataDefinitionType.LINK,
                ]:
                    target_attributes_columns.append((label_name_en, attribute_name_en))

        return target_attributes_columns


def get_frame_no_map(task_json_path: Path) -> dict[tuple[str, str], int]:
    """
    タスクJSONファイルから、(task_id, input_data_id)をキーとし、フレーム番号を値とするマップを取得します。
    フレーム番号は1始まりです。

    Args:
        task_json_path: タスクJSONファイルのパス

    Returns:
        key: (task_id, input_data_id)のタプル、value: フレーム番号のdict
    """
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
