# pylint: disable=too-many-lines
from __future__ import annotations

import abc
import argparse
import collections
import copy
import json
import logging
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Optional, Union

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole, TaskPhase, TaskStatus
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

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    convert_annotation_specs_labels_v2_to_v1,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json
from annofabcli.common.visualize import AddProps, MessageLocale

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


class CsvType(Enum):
    """出力するCSVの種類"""

    LABEL = "label"
    """ラベルごとのアノテーション数を出力"""
    ATTRIBUTE = "attribute"
    """属性値ごとのアノテーション数を出力"""


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
    annotation_count: int
    annotation_count_by_label: Counter[str]
    annotation_count_by_attribute: Counter[AttributeValueKey] = field(
        metadata=config(
            encoder=encode_annotation_count_by_attribute,
        )
    )


@dataclass(frozen=True)
class AnnotationCounterByTask(AnnotationCounter, DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    input_data_count: int


@dataclass(frozen=True)
class AnnotationCounterByInputData(AnnotationCounter, DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    frame_no: Optional[int] = None
    """アノテーションJSONには含まれていない情報なので、Optionalにする"""


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
        target_labels: 集計対象のラベル（label_name_en）
        target_attribute_names: 集計対象の属性名
        non_target_labels: 集計対象外のラベル
        non_target_attribute_names: 集計対象外の属性名のキー。
        frame_no_map: key:task_id,input_data_idのtuple, value:フレーム番号

    """

    def __init__(
        self,
        *,
        target_labels: Optional[Collection[str]] = None,
        non_target_labels: Optional[Collection[str]] = None,
        target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
        non_target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
        frame_no_map: Optional[dict[tuple[str, str], int]] = None,
    ) -> None:
        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None
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

        def convert_attribute_value_to_key(value: Union[bool, str, float]) -> str:  # noqa: FBT001
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
        if self.target_attribute_names is not None:
            annotation_count_by_attribute = collections.Counter(
                {
                    (label, attribute_name, attribute_value): count
                    for (label, attribute_name, attribute_value), count in annotation_count_by_attribute.items()
                    if (label, attribute_name) in self.target_attribute_names
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
        frame_no: Optional[int] = None
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
            annotation_count=sum(annotation_count_by_label.values()),
            annotation_count_by_label=annotation_count_by_label,
            annotation_count_by_attribute=annotation_count_by_attribute,
            frame_no=frame_no,
        )

    def get_annotation_counter_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
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
    """タスク単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。"""

    def __init__(
        self,
        *,
        target_labels: Optional[Collection[str]] = None,
        non_target_labels: Optional[Collection[str]] = None,
        target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
        non_target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
    ) -> None:
        self.counter_by_input_data = ListAnnotationCounterByInputData(
            target_labels=target_labels,
            non_target_labels=non_target_labels,
            target_attribute_names=target_attribute_names,
            non_target_attribute_names=non_target_attribute_names,
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
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> list[AnnotationCounterByTask]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        """

        counter_list = []
        iter_task_parser = lazy_parse_simple_annotation_by_task(annotation_path)

        target_task_ids = set(target_task_ids) if target_task_ids is not None else None

        logger.debug("アノテーションzip/ディレクトリを読み込み中")
        for task_index, task_parser in enumerate(iter_task_parser):
            if (task_index + 1) % 1000 == 0:
                logger.debug(f"{task_index + 1}  件目のタスクディレクトリを読み込み中")

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

            task_counter = self.get_annotation_counter(task_parser)
            counter_list.append(task_counter)

        return counter_list


class AttributeCountCsv:
    """
    属性値ごとのアノテーション数を記載するCSV。

    Args:
        selective_attribute_value_max_count: 選択肢系の属性の値の個数の上限。これを超えた場合は、非選択肢系属性（トラッキングIDやアノテーションリンクなど）とみなす

    """

    def __init__(self, selective_attribute_value_max_count: int = 20) -> None:
        self.selective_attribute_value_max_count = selective_attribute_value_max_count

    def _only_selective_attribute(self, columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
        """
        選択肢系の属性に対応する列のみ抽出する。
        属性値の個数が多い場合、非選択肢系の属性（トラッキングIDやアノテーションリンクなど）の可能性があるため、それらを除外する。
        CSVの列数を増やしすぎないための対策。
        """
        attribute_name_list: list[AttributeNameKey] = []
        for label, attribute_name, _ in columns:
            attribute_name_list.append((label, attribute_name))

        non_selective_attribute_names = {key for key, value in collections.Counter(attribute_name_list).items() if value > self.selective_attribute_value_max_count}
        if len(non_selective_attribute_names) > 0:
            logger.debug(f"以下の属性は値の個数が{self.selective_attribute_value_max_count}を超えていたため、集計しません。 :: {non_selective_attribute_names}")

        return [(label, attribute_name, attribute_value) for (label, attribute_name, attribute_value) in columns if (label, attribute_name) not in non_selective_attribute_names]

    def _value_columns(self, counter_list: Collection[AnnotationCounter], prior_attribute_columns: Optional[list[AttributeValueKey]]) -> list[AttributeValueKey]:
        all_attr_key_set = {attr_key for c in counter_list for attr_key in c.annotation_count_by_attribute}
        if prior_attribute_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_attribute_columns))
            remaining_columns_only_selective_attribute = self._only_selective_attribute(remaining_columns)

            # `remaining_columns_only_selective_attribute`には、属性値が空である列などが格納されている
            # `remaining_columns_only_selective_attribute`を、`value_columns`の関連している位置に挿入する。
            value_columns = copy.deepcopy(prior_attribute_columns)
            for remaining_column in remaining_columns_only_selective_attribute:
                is_inserted = False
                for i in range(len(value_columns) - 1, -1, -1):
                    col = value_columns[i]
                    if col[0:2] == remaining_column[0:2]:
                        value_columns.insert(i + 1, remaining_column)
                        is_inserted = True
                        break
                if not is_inserted:
                    value_columns.append(remaining_column)

            assert len(value_columns) == len(prior_attribute_columns) + len(remaining_columns_only_selective_attribute)

        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = self._only_selective_attribute(remaining_columns)

        # 重複している場合は、重複要素を取り除く。ただし元の順番は維持する
        value_columns = list(dict.fromkeys(value_columns).keys())
        return value_columns

    def print_csv_by_task(
        self,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> None:
        def get_columns() -> list[AttributeValueKey]:
            basic_columns = [
                ("project_id", "", ""),
                ("task_id", "", ""),
                ("task_status", "", ""),
                ("task_phase", "", ""),
                ("task_phase_stage", "", ""),
                ("input_data_count", "", ""),
                ("annotation_count", "", ""),
            ]
            value_columns = self._value_columns(counter_list, prior_attribute_columns)
            return basic_columns + value_columns

        def to_cell(c: AnnotationCounterByTask) -> dict[AttributeValueKey, Any]:
            cell = {
                ("project_id", "", ""): c.project_id,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("input_data_count", "", ""): c.input_data_count,
                ("annotation_count", "", ""): c.annotation_count,
            }
            cell.update(c.annotation_count_by_attribute)
            return cell

        columns = get_columns()
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # `task_id`列など`basic_columns`も`fillna`対象だが、nanではないはずので問題ない
        df.fillna(0, inplace=True)

        print_csv(df, output=str(output_file))

    def print_csv_by_input_data(
        self,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> None:
        def get_columns() -> list[AttributeValueKey]:
            basic_columns = [
                ("project_id", "", ""),
                ("task_id", "", ""),
                ("task_status", "", ""),
                ("task_phase", "", ""),
                ("task_phase_stage", "", ""),
                ("input_data_id", "", ""),
                ("input_data_name", "", ""),
                ("frame_no", "", ""),
                ("annotation_count", "", ""),
            ]
            value_columns = self._value_columns(counter_list, prior_attribute_columns)
            return basic_columns + value_columns

        def to_cell(c: AnnotationCounterByInputData) -> dict[tuple[str, str, str], Any]:
            cell = {
                ("project_id", "", ""): c.project_id,
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("frame_no", "", ""): c.frame_no,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("annotation_count", "", ""): c.annotation_count,
            }
            cell.update(c.annotation_count_by_attribute)

            return cell

        columns = get_columns()
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(counter_list, prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))

        print_csv(df, output=str(output_file))


class LabelCountCsv:
    """
    ラベルごとのアノテーション数を記載するCSV。


    """

    def _value_columns(self, counter_list: Collection[AnnotationCounter], prior_label_columns: Optional[list[str]]) -> list[str]:
        all_attr_key_set = {attr_key for c in counter_list for attr_key in c.annotation_count_by_label}
        if prior_label_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_label_columns))
            value_columns = prior_label_columns + remaining_columns
        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = remaining_columns

        return value_columns

    def print_csv_by_task(
        self,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        prior_label_columns: Optional[list[str]] = None,
    ) -> None:
        def get_columns() -> list[str]:
            basic_columns = [
                "project_id",
                "task_id",
                "task_status",
                "task_phase",
                "task_phase_stage",
                "input_data_count",
                "annotation_count",
            ]
            value_columns = self._value_columns(counter_list, prior_label_columns)
            return basic_columns + value_columns

        def to_dict(c: AnnotationCounterByTask) -> dict[str, Any]:
            d = {
                "project_id": c.project_id,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "input_data_count": c.input_data_count,
                "annotation_count": c.annotation_count,
            }
            # キーをラベル名、値をラベルごとのアノテーション数にしたdictに変換する
            d.update(c.annotation_count_by_label)
            return d

        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=get_columns())

        # NaNを0に変換する
        # `basic_columns`は必ずnanではないので、すべての列に対してfillnaを実行しても問題ないはず
        df.fillna(0, inplace=True)
        print_csv(df, output=str(output_file))

    def print_csv_by_input_data(
        self,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        prior_label_columns: Optional[list[str]] = None,
    ) -> None:
        def get_columns() -> list[str]:
            basic_columns = [
                "project_id",
                "task_id",
                "task_status",
                "task_phase",
                "task_phase_stage",
                "input_data_id",
                "input_data_name",
                "frame_no",
                "annotation_count",
            ]
            value_columns = self._value_columns(counter_list, prior_label_columns)
            return basic_columns + value_columns

        def to_dict(c: AnnotationCounterByInputData) -> dict[str, Any]:
            d = {
                "project_id": c.project_id,
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "frame_no": c.frame_no,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "annotation_count": c.annotation_count,
            }
            d.update(c.annotation_count_by_label)
            return d

        columns = get_columns()
        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=columns)

        # アノテーション数列のNaNを0に変換する
        value_columns = self._value_columns(counter_list, prior_label_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))

        print_csv(df, output=str(output_file))


class AnnotationSpecs:
    """

    Args:
        annotation_type: 出力対象のラベルの種類。

    """

    def __init__(self, service: annofabapi.Resource, project_id: str, *, annotation_type: Optional[str] = None) -> None:
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

    def attribute_name_keys(
        self,
        excluded_attribute_types: Optional[Collection[AdditionalDataDefinitionType]] = None,
        include_attribute_types: Optional[Collection[AdditionalDataDefinitionType]] = None,
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

    def selective_attribute_value_keys(self) -> list[AttributeValueKey]:
        """
        選択系の属性の属性値のキーの一覧。

        以下の属性種類
        * ドロップダウン
        * ラジオボタン
        * チェックボックス
        """
        target_attribute_value_keys = []
        for label in self._labels_v1:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""

            for attribute in label["additional_data_definitions"]:
                attribute_name_en = AddProps.get_message(attribute["name"], MessageLocale.EN)
                attribute_name_en = attribute_name_en if attribute_name_en is not None else ""

                if AdditionalDataDefinitionType(attribute["type"]) in [
                    AdditionalDataDefinitionType.CHOICE,
                    AdditionalDataDefinitionType.SELECT,
                ]:
                    for choice in attribute["choices"]:
                        choice_name_en = AddProps.get_message(choice["name"], MessageLocale.EN)
                        choice_name_en = choice_name_en if choice_name_en is not None else ""
                        target_attribute_value_keys.append((label_name_en, attribute_name_en, choice_name_en))

                elif AdditionalDataDefinitionType(attribute["type"]) == AdditionalDataDefinitionType.FLAG:
                    target_attribute_value_keys.extend([(label_name_en, attribute_name_en, "true"), (label_name_en, attribute_name_en, "false")])

                else:
                    continue

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


class ListAnnotationCountMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    @staticmethod
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

    def print_annotation_counter_csv_by_input_data(
        self,
        annotation_path: Path,
        csv_type: CsvType,
        output_file: Path,
        *,
        project_id: Optional[str] = None,
        task_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        # アノテーション仕様の非選択系の属性は、集計しないようにする。集計しても意味がないため。
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        frame_no_map = self.get_frame_no_map(task_json_path) if task_json_path is not None else None
        counter_by_input_data = ListAnnotationCounterByInputData(non_target_attribute_names=non_selective_attribute_name_keys, frame_no_map=frame_no_map)
        counter_list_by_input_data = counter_by_input_data.get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        if csv_type == CsvType.LABEL:
            # ラベル名の列順が、アノテーション仕様にあるラベル名の順番に対応するようにする。
            label_columns: Optional[list[str]] = None
            if annotation_specs is not None:
                label_columns = annotation_specs.label_keys()

            LabelCountCsv().print_csv_by_input_data(counter_list_by_input_data, output_file, prior_label_columns=label_columns)
        elif csv_type == CsvType.ATTRIBUTE:
            attribute_columns: Optional[list[AttributeValueKey]] = None
            if annotation_specs is not None:
                attribute_columns = annotation_specs.selective_attribute_value_keys()

            AttributeCountCsv().print_csv_by_input_data(counter_list_by_input_data, output_file, prior_attribute_columns=attribute_columns)

    def print_annotation_counter_csv_by_task(
        self,
        annotation_path: Path,
        csv_type: CsvType,
        output_file: Path,
        *,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        # アノテーション仕様の非選択系の属性は、集計しないようにする。集計しても意味がないため。
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        counter_list_by_task = ListAnnotationCounterByTask(non_target_attribute_names=non_selective_attribute_name_keys).get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        if csv_type == CsvType.LABEL:
            # 列順が、アノテーション仕様にあるラベル名の順番に対応するようにする。
            label_columns: Optional[list[str]] = None
            if annotation_specs is not None:
                label_columns = annotation_specs.label_keys()

            LabelCountCsv().print_csv_by_task(counter_list_by_task, output_file, prior_label_columns=label_columns)

        elif csv_type == CsvType.ATTRIBUTE:
            # 列順が、アノテーション仕様にある属性名と属性値の順番に対応するようにする。
            attribute_columns: Optional[list[AttributeValueKey]] = None
            if annotation_specs is not None:
                attribute_columns = annotation_specs.selective_attribute_value_keys()

            AttributeCountCsv().print_csv_by_task(counter_list_by_task, output_file, prior_attribute_columns=attribute_columns)

    def print_annotation_counter_json_by_input_data(
        self,
        annotation_path: Path,
        output_file: Path,
        *,
        project_id: Optional[str] = None,
        task_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        json_is_pretty: bool = False,
    ) -> None:
        """ラベルごと/属性ごとのアノテーション数を入力データ単位でJSONファイルに出力します。"""

        # アノテーション仕様の非選択系の属性は、集計しないようにする。集計しても意味がないため。
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()
        else:
            non_selective_attribute_name_keys = None

        frame_no_map = self.get_frame_no_map(task_json_path) if task_json_path is not None else None
        counter_list_by_input_data = ListAnnotationCounterByInputData(non_target_attribute_names=non_selective_attribute_name_keys, frame_no_map=frame_no_map).get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        print_json(
            [e.to_dict(encode_json=True) for e in counter_list_by_input_data],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    def print_annotation_counter_json_by_task(
        self,
        annotation_path: Path,
        output_file: Path,
        *,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        json_is_pretty: bool = False,
    ) -> None:
        """ラベルごと/属性ごとのアノテーション数をタスク単位でJSONファイルに出力します。"""

        # アノテーション仕様の非選択系の属性は、集計しないようにする。集計しても意味がないため。
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()
        else:
            non_selective_attribute_name_keys = None

        counter_list_by_task = ListAnnotationCounterByTask(
            non_target_attribute_names=non_selective_attribute_name_keys,
        ).get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        print_json(
            [e.to_dict(encode_json=True) for e in counter_list_by_task],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    def print_annotation_counter(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        output_file: Path,
        arg_format: FormatArgument,
        *,
        project_id: Optional[str] = None,
        task_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        csv_type: Optional[CsvType] = None,
    ) -> None:
        """ラベルごと/属性ごとのアノテーション数を出力します。"""
        if arg_format == FormatArgument.CSV:
            assert csv_type is not None
            if group_by == GroupBy.INPUT_DATA_ID:
                self.print_annotation_counter_csv_by_input_data(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    task_json_path=task_json_path,
                    output_file=output_file,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    csv_type=csv_type,
                )

            elif group_by == GroupBy.TASK_ID:
                self.print_annotation_counter_csv_by_task(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    output_file=output_file,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    csv_type=csv_type,
                )

        elif arg_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
            json_is_pretty = arg_format == FormatArgument.PRETTY_JSON

            if group_by == GroupBy.INPUT_DATA_ID:
                self.print_annotation_counter_json_by_input_data(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    task_json_path=task_json_path,
                    output_file=output_file,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    json_is_pretty=json_is_pretty,
                )

            elif group_by == GroupBy.TASK_ID:
                self.print_annotation_counter_json_by_task(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    output_file=output_file,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    json_is_pretty=json_is_pretty,
                )


class ListAnnotationCount(CommandLine):
    """
    アノテーション数情報を出力する。
    """

    COMMON_MESSAGE = "annofabcli statistics list_annotation_count: error:"

    def validate(self, args: argparse.Namespace) -> bool:
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

        project_id: Optional[str] = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        group_by = GroupBy(args.group_by)
        csv_type = CsvType(args.type)
        output_file: Path = args.output
        arg_format = FormatArgument(args.format)
        main_obj = ListAnnotationCountMain(self.service)

        downloading_obj = DownloadingFile(self.service)

        # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
        # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
        with tempfile.TemporaryDirectory() as str_temp_dir:
            # タスク全件ファイルは、フレーム番号を参照するのに利用する
            if project_id is not None:
                task_json_path = Path(str_temp_dir) / f"{project_id}__task.json"
                downloading_obj.download_task_json(
                    project_id,
                    dest_path=str(task_json_path),
                )
            else:
                task_json_path = None

            func = partial(
                main_obj.print_annotation_counter,
                project_id=project_id,
                task_json_path=task_json_path,
                group_by=group_by,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
            )

            if annotation_path is None:
                assert project_id is not None
                annotation_path = Path(str_temp_dir) / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=str(annotation_path),
                    is_latest=args.latest,
                )
                func(annotation_path=annotation_path)
            else:
                func(annotation_path=annotation_path)


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

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=[e.value for e in CsvType],
        default=CsvType.LABEL.value,
        help="出力するCSVの種類を指定してください。 ``--format csv`` を指定したときのみ有効なオプションです。\n"
        "\n"
        "* label: ラベルごとにアノテーション数が記載されているCSV\n"
        "* attribute: 属性値ごとにアノテーション数が記載されているCSV",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_count"
    subcommand_help = "ラベルごとまたは属性値ごとにアノテーション数を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
