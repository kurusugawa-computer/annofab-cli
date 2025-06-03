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
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Literal, Optional, Protocol, Union

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
from annofabapi.pydantic_models.additional_data_definition_type import AdditionalDataDefinitionType
from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus
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
from annofabcli.common.type_util import assert_noreturn
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

    annotation_attribute_counts: dict[AttributeValueKey, int] = field(
        metadata=config(
            encoder=encode_annotation_count_by_attribute,
        )
    )
    """属性値ごとのアノテーションの個数
    key: tuple[ラベル名(英語),属性名(英語),属性値の種類], value: アノテーション数
    """
    frame_no: Optional[int] = None
    """フレーム番号（1始まり）。アノテーションJSONには含まれていない情報なので、Optionalにする"""


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


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
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

    def get_annotation_count(self, simple_annotation: dict[str, Any]) -> AnnotationCountByInputData:
        """
        1個のアノテーションJSONに対して、属性値ごとのアノテーション数を取得します。

        Args:
            simple_annotation: アノテーションJSONファイルの内容

        """

        def convert_attribute_value_to_type(value: Optional[Union[bool, str, float]]) -> AttributeValueType:  # noqa: FBT001
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

        frame_no: Optional[int] = None
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
        )

    def get_annotation_count_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
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


class AnnotationCountCsvByAttribute:
    """
    属性値ごとのアノテーション数をCSVに出力するためのクラス

    Args:
        selective_attribute_value_max_count: 選択肢系の属性の値の個数の上限。これを超えた場合は、非選択肢系属性（トラッキングIDやアノテーションリンクなど）とみなす

    """

    def __init__(self, selective_attribute_value_max_count: int = 20) -> None:
        self.selective_attribute_value_max_count = selective_attribute_value_max_count

    def _value_columns(self, annotation_count_list: Collection[HasAnnotationAttributeCounts], *, prior_attribute_columns: Optional[list[tuple[str, str, str]]]) -> list[tuple[str, str, str]]:
        """
        CSVの数値列を取得します。
        """
        all_attr_key_set = {attr_key for c in annotation_count_list for attr_key in c.annotation_attribute_counts}
        if prior_attribute_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_attribute_columns))  # type: ignore[arg-type]
            value_columns = prior_attribute_columns + remaining_columns

        else:
            value_columns = sorted(all_attr_key_set)

        # 重複している場合は、重複要素を取り除く。ただし元の順番は維持する
        value_columns = list(dict.fromkeys(value_columns).keys())
        return value_columns

    def get_columns_by_input_data(
        self,
        annotation_count_list: list[AnnotationCountByInputData],
        prior_attribute_columns: Optional[list[tuple[str, str, str]]] = None,
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
        ]
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns=prior_attribute_columns)
        return basic_columns + value_columns

    def get_columns_by_task(
        self,
        annotation_count_list: list[AnnotationCountByTask],
        prior_attribute_columns: Optional[list[tuple[str, str, str]]] = None,
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
        prior_attribute_columns: Optional[list[tuple[str, str, str]]] = None,
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
        prior_attribute_columns: Optional[list[tuple[str, str, str]]] = None,
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


class ListAnnotationAttributeFilledCountMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def print_annotation_count_csv_by_input_data(self, annotation_count_list: list[AnnotationCountByInputData], output_file: Path, *, attribute_names: Optional[list[tuple[str, str]]]) -> None:
        attribute_columns: Optional[list[tuple[str, str, str]]] = None
        if attribute_names is not None:
            attribute_columns = get_attribute_columns(attribute_names)

        df = AnnotationCountCsvByAttribute().create_df_by_input_data(annotation_count_list, prior_attribute_columns=attribute_columns)
        print_csv(df, output_file)

    def print_annotation_count_csv_by_task(self, annotation_count_list: list[AnnotationCountByTask], output_file: Path, *, attribute_names: Optional[list[tuple[str, str]]]) -> None:
        attribute_columns: Optional[list[tuple[str, str, str]]] = None
        if attribute_names is not None:
            attribute_columns = get_attribute_columns(attribute_names)

        df = AnnotationCountCsvByAttribute().create_df_by_task(annotation_count_list, prior_attribute_columns=attribute_columns)
        print_csv(df, output_file)

    def print_annotation_count(
        self,
        annotation_path: Path,
        output_file: Path,
        group_by: GroupBy,
        output_format: FormatArgument,
        *,
        project_id: Optional[str] = None,
        include_flag_attribute: bool = False,
        task_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        annotation_specs: Optional[AnnotationSpecs] = None
        target_attribute_names: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            if not include_flag_attribute:
                target_attribute_names = annotation_specs.attribute_name_keys(excluded_attribute_types=[AdditionalDataDefinitionType.FLAG])

        frame_no_map = get_frame_no_map(task_json_path) if task_json_path is not None else None

        annotation_count_list_by_input_data = ListAnnotationCounterByInputData(frame_no_map=frame_no_map, target_attribute_names=target_attribute_names).get_annotation_count_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        if group_by == GroupBy.INPUT_DATA_ID:
            logger.info(f"{len(annotation_count_list_by_input_data)} 件の入力データに含まれるアノテーション数の情報を出力します。")
            if output_format == FormatArgument.CSV:
                self.print_annotation_count_csv_by_input_data(annotation_count_list_by_input_data, output_file=output_file, attribute_names=target_attribute_names)

            elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
                json_is_pretty = output_format == FormatArgument.PRETTY_JSON

                print_json(
                    [e.to_dict(encode_json=True) for e in annotation_count_list_by_input_data],
                    is_pretty=json_is_pretty,
                    output=output_file,
                )
        elif group_by == GroupBy.TASK_ID:
            annotation_count_list_by_task = convert_annotation_count_list_by_input_data_to_by_task(annotation_count_list_by_input_data)
            logger.info(f"{len(annotation_count_list_by_task)} 件のタスクに含まれるアノテーション数の情報を出力します。")
            if output_format == FormatArgument.CSV:
                self.print_annotation_count_csv_by_task(annotation_count_list_by_task, output_file=output_file, attribute_names=target_attribute_names)

            elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
                json_is_pretty = output_format == FormatArgument.PRETTY_JSON

                print_json(
                    [e.to_dict(encode_json=True) for e in annotation_count_list_by_task],
                    is_pretty=json_is_pretty,
                    output=output_file,
                )

        else:
            raise assert_noreturn(group_by)


class ListAnnotationAttributeFilledCount(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation list_annotation_attribute_filled_count: error:"

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
        output_file: Path = args.output
        output_format = FormatArgument(args.format)
        main_obj = ListAnnotationAttributeFilledCountMain(self.service)

        downloading_obj = DownloadingFile(self.service)

        # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
        # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
        with tempfile.TemporaryDirectory() as str_temp_dir:
            # タスク全件ファイルは、フレーム番号を参照するのに利用する
            if project_id is not None and group_by == GroupBy.INPUT_DATA_ID:
                # group_byで条件を絞り込んでいる理由：
                # タスクIDで集計する際は、フレーム番号は出力しないので、タスク全件ファイルをダウンロードする必要はないため
                task_json_path = Path(str_temp_dir) / f"{project_id}__task.json"
                downloading_obj.download_task_json(
                    project_id,
                    dest_path=str(task_json_path),
                )
            else:
                task_json_path = None

            func = partial(
                main_obj.print_annotation_count,
                project_id=project_id,
                task_json_path=task_json_path,
                group_by=group_by,
                output_format=output_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                include_flag_attribute=args.include_flag_attribute,
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


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationAttributeFilledCount(service, facade, args).main()


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
        "--include_flag_attribute",
        action="store_true",
        help="指定した場合は、On/Off属性（チェックボックス）も集計対象にします。"
        "On/Off属性は基本的に常に「入力されている」と判定されるため、デフォルトでは集計対象外にしています。"
        "``--project_id`` が指定されているときのみ有効なオプションです。",
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


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_attribute_filled_count"
    subcommand_help = "値が入力されている属性の個数を、タスクごとまたは入力データごとに集計します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
