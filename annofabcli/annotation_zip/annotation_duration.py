# pylint: disable=too-many-lines
from __future__ import annotations

import collections
import json
import logging
import zipfile
from collections import defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from annofabapi.models import TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
from dataclasses_json import DataClassJsonMixin, config

from annofabcli.common.facade import (
    TaskQuery,
    match_annotation_with_task_query,
)

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
