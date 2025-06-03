# pylint: disable=too-many-lines
from __future__ import annotations

import argparse
import collections
import copy
import json
import logging
import sys
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

import annofabapi
import pandas
from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole, TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
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
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json
from annofabcli.statistics.list_annotation_count import AnnotationSpecs

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
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    video_duration_second: Optional[float]
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
        target_labels: Optional[Collection[str]] = None,
        non_target_labels: Optional[Collection[str]] = None,
        target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
        non_target_attribute_names: Optional[Collection[AttributeNameKey]] = None,
    ) -> None:
        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None

    def get_annotation_duration(self, simple_annotation: dict[str, Any], video_duration_second: Optional[float] = None) -> AnnotationDuration:
        """
        1個のアノテーションJSONに対して、ラベルごと/属性ごとの区間アノテーションの長さを取得する。

        Args:
            simple_annotation: アノテーションJSONファイルの内容
            video_duration_second: 動画の長さ[秒]
        """

        def calculate_annotation_duration_second(detail: dict[str, Any]) -> float:
            """区間アノテーションのdetail情報から、区間アノテーションの長さ（秒）を計算する"""
            return (detail["data"]["end"] - detail["data"]["begin"]) / 1000

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
            video_duration_second=video_duration_second,
            annotation_duration_second=sum(annotation_duration_by_label.values()),
            annotation_duration_second_by_label=annotation_duration_by_label,
            annotation_duration_second_by_attribute=annotation_duration_by_attribute,
        )

    def get_annotation_duration_list(
        self,
        annotation_path: Path,
        *,
        input_data_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> list[AnnotationDuration]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとの区間アノテーションの長さを取得する。

        Args:
            input_data_json_path: 入力データ全件ファイルのパス。動画の長さを取得するのに利用します。
        """
        dict_input_data: Optional[dict[str, dict[str, Any]]] = None
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

            video_duration_second: Optional[float] = None
            if dict_input_data is not None:
                input_data = dict_input_data[parser.input_data_id]
                video_duration_second = input_data["system_metadata"]["input_duration"]

            annotation_duration = self.get_annotation_duration(simple_annotation_dict, video_duration_second=video_duration_second)
            annotation_duration_list.append(annotation_duration)

        return annotation_duration_list


class AnnotationDurationCsvByAttribute:
    """
    属性値ごとのアノテーション長さをCSVに出力するためのクラス

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

    def _value_columns(self, annotation_duration_list: Collection[AnnotationDuration], prior_attribute_columns: Optional[list[AttributeValueKey]]) -> list[AttributeValueKey]:
        all_attr_key_set = {attr_key for c in annotation_duration_list for attr_key in c.annotation_duration_second_by_attribute}
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

    def get_columns(
        self,
        annotation_duration_list: list[AnnotationDuration],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> list[AttributeValueKey]:
        basic_columns = [
            ("project_id", "", ""),
            ("task_id", "", ""),
            ("task_status", "", ""),
            ("task_phase", "", ""),
            ("task_phase_stage", "", ""),
            ("input_data_id", "", ""),
            ("input_data_name", "", ""),
            ("video_duration_second", "", ""),
            ("annotation_duration_second", "", ""),
        ]
        value_columns = self._value_columns(annotation_duration_list, prior_attribute_columns)
        return basic_columns + value_columns

    def create_df(
        self,
        annotation_duration_list: list[AnnotationDuration],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> pandas.DataFrame:
        def to_cell(c: AnnotationDuration) -> dict[tuple[str, str, str], Any]:
            cell: dict[AttributeValueKey, Any] = {
                ("project_id", "", ""): c.project_id,
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("video_duration_second", "", ""): c.video_duration_second,
                ("annotation_duration_second", "", ""): c.annotation_duration_second,
            }
            cell.update(c.annotation_duration_second_by_attribute)

            return cell

        columns = self.get_columns(annotation_duration_list, prior_attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in annotation_duration_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(annotation_duration_list, prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df


class AnnotationDurationCsvByLabel:
    """
    ラベルごとのアノテーション長さをCSVとして出力するためのクラス。
    """

    def _value_columns(self, annotation_duration_list: list[AnnotationDuration], prior_label_columns: Optional[list[str]]) -> list[str]:
        all_attr_key_set = {attr_key for elm in annotation_duration_list for attr_key in elm.annotation_duration_second_by_label.keys()}  # noqa: SIM118
        if prior_label_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_label_columns))
            value_columns = prior_label_columns + remaining_columns
        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = remaining_columns

        return value_columns

    def get_columns(
        self,
        annotation_duration_list: list[AnnotationDuration],
        prior_label_columns: Optional[list[str]] = None,
    ) -> list[str]:
        basic_columns = [
            "project_id",
            "task_id",
            "task_status",
            "task_phase",
            "task_phase_stage",
            "input_data_id",
            "input_data_name",
            "video_duration_second",
            "annotation_duration_second",
        ]
        value_columns = self._value_columns(annotation_duration_list, prior_label_columns)
        return basic_columns + value_columns

    def create_df(
        self,
        annotation_duration_list: list[AnnotationDuration],
        prior_label_columns: Optional[list[str]] = None,
    ) -> pandas.DataFrame:
        def to_dict(c: AnnotationDuration) -> dict[str, Any]:
            d: dict[str, Any] = {
                "project_id": c.project_id,
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "video_duration_second": c.video_duration_second,
                "annotation_duration_second": c.annotation_duration_second,
            }
            d.update(c.annotation_duration_second_by_label)
            return d

        columns = self.get_columns(annotation_duration_list, prior_label_columns)
        df = pandas.DataFrame([to_dict(e) for e in annotation_duration_list], columns=columns)

        # アノテーション数列のNaNを0に変換する
        value_columns = self._value_columns(annotation_duration_list, prior_label_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))

        return df


class ListAnnotationDurationMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def print_annotation_duration_csv(self, annotation_duration_list: list[AnnotationDuration], csv_type: CsvType, output_file: Path, *, annotation_specs: Optional[AnnotationSpecs]) -> None:
        if csv_type == CsvType.LABEL:
            # ラベル名の列順が、アノテーション仕様にあるラベル名の順番に対応するようにする。
            label_columns: Optional[list[str]] = None
            if annotation_specs is not None:
                label_columns = annotation_specs.label_keys()

            df = AnnotationDurationCsvByLabel().create_df(annotation_duration_list, prior_label_columns=label_columns)
        elif csv_type == CsvType.ATTRIBUTE:
            attribute_columns: Optional[list[AttributeValueKey]] = None
            if annotation_specs is not None:
                attribute_columns = annotation_specs.selective_attribute_value_keys()

            df = AnnotationDurationCsvByAttribute().create_df(annotation_duration_list, prior_attribute_columns=attribute_columns)

        else:
            raise RuntimeError(f"{csv_type=}はサポートしていません。")

        print_csv(df, output_file)

    def print_annotation_duration(
        self,
        annotation_path: Path,
        output_file: Path,
        arg_format: FormatArgument,
        *,
        project_id: Optional[str] = None,
        input_data_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        csv_type: Optional[CsvType] = None,
    ) -> None:
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id, annotation_type=DefaultAnnotationType.RANGE.value)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        annotation_duration_list = ListAnnotationDurationByInputData(non_target_attribute_names=non_selective_attribute_name_keys).get_annotation_duration_list(
            annotation_path,
            input_data_json_path=input_data_json_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        logger.info(f"{len(annotation_duration_list)} 件のタスクに含まれる区間アノテーションの長さ情報を出力します。")

        if arg_format == FormatArgument.CSV:
            assert csv_type is not None
            self.print_annotation_duration_csv(annotation_duration_list, output_file=output_file, csv_type=csv_type, annotation_specs=annotation_specs)

        elif arg_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
            json_is_pretty = arg_format == FormatArgument.PRETTY_JSON

            print_json(
                [e.to_dict(encode_json=True) for e in annotation_duration_list],
                is_pretty=json_is_pretty,
                output=output_file,
            )


class ListAnnotationDuration(CommandLine):
    """
    区間アノテーションの長さ情報を出力する。
    """

    COMMON_MESSAGE = "annofabcli statistics list_annotation_duration: error:"

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
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                logger.warning(f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので、出力される区間アノテーションの長さはすべて0秒になります。")

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        csv_type = CsvType(args.type)
        output_file: Path = args.output
        arg_format = FormatArgument(args.format)
        main_obj = ListAnnotationDurationMain(self.service)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_duration(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Optional[Path]) -> None:
            if annotation_path is None:
                annotation_path = temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=is_latest,
                )

            input_data_json_path = temp_dir / f"{project_id}__input_data.json"
            downloading_obj.download_input_data_json(
                project_id,
                dest_path=input_data_json_path,
                is_latest=is_latest,
            )

            main_obj.print_annotation_duration(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
                input_data_json_path=input_data_json_path,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_duration(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_duration(project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            assert annotation_path is not None
            main_obj.print_annotation_duration(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
                input_data_json_path=None,
            )


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
        help="project_id。``--annotation`` が未指定のときは必須です。\n"
        "``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やCSV列順が決まります。"
        "また、動画の長さ( ``video_duration_second`` )も出力します。",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=[e.value for e in CsvType],
        default=CsvType.LABEL.value,
        help="出力するCSVの種類を指定してください。 ``--format csv`` を指定したときのみ有効なオプションです。\n"
        "\n"
        "* label: ラベルごとに区間アノテーションの長さが記載されているCSV\n"
        "* attribute: 属性値ごとに区間アノテーションの長さが記載されているCSV",
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

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationDuration(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_duration"
    subcommand_help = "ラベルごとまたは属性値ごとに区間アノテーションの長さ（秒）を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
