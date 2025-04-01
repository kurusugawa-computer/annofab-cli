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
from dataclasses import field
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Literal, Optional, Union

import annofabapi
import pandas
from annofabapi.models import DefaultAnnotationType, ProjectMemberRole, TaskPhase, TaskStatus
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


class AnnotationCount(DataClassJsonMixin):
    """
    入力データまたはタスク単位の区間アノテーションの長さ情報。
    """

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


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


class ListAnnotationCountByInputData:
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
    ) -> None:
        self.target_labels = set(target_labels) if target_labels is not None else None
        self.target_attribute_names = set(target_attribute_names) if target_attribute_names is not None else None
        self.non_target_labels = set(non_target_labels) if non_target_labels is not None else None
        self.non_target_attribute_names = set(non_target_attribute_names) if non_target_attribute_names is not None else None

    def get_annotation_count(self, simple_annotation: dict[str, Any]) -> AnnotationCount:
        """
        1個のアノテーションJSONに対して、属性値ごとのアノテーション数を取得します。

        Args:
            simple_annotation: アノテーションJSONファイルの内容

        TODO アノテーションの種類を限定する？チェックボックスに関しては興味がないはず
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

        return AnnotationCount(
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            annotation_count_by_attribute=annotation_count_by_attribute,
        )

    def get_annotation_count_list(
        self,
        annotation_path: Path,
        *,
        input_data_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> list[AnnotationCount]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、属性値ごとのアノテーション数を取得する。

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

            annotation_count = self.get_annotation_count(simple_annotation_dict)
            annotation_duration_list.append(annotation_count)

        return annotation_duration_list


class AnnotationCountCsvByAttribute:
    """
    属性値ごとのアノテーション数をCSVに出力するためのクラス

    Args:
        selective_attribute_value_max_count: 選択肢系の属性の値の個数の上限。これを超えた場合は、非選択肢系属性（トラッキングIDやアノテーションリンクなど）とみなす

    """  # noqa: E501

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

        non_selective_attribute_names = {
            key for key, value in collections.Counter(attribute_name_list).items() if value > self.selective_attribute_value_max_count
        }
        if len(non_selective_attribute_names) > 0:
            logger.debug(
                f"以下の属性は値の個数が{self.selective_attribute_value_max_count}を超えていたため、集計しません。 :: {non_selective_attribute_names}"
            )

        return [
            (label, attribute_name, attribute_value)
            for (label, attribute_name, attribute_value) in columns
            if (label, attribute_name) not in non_selective_attribute_names
        ]

    def _value_columns(
        self, annotation_duration_list: Collection[AnnotationCount], prior_attribute_columns: Optional[list[AttributeValueKey]]
    ) -> list[AttributeValueKey]:
        """
        TODO 見直す
        """
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
        annotation_count_list: list[AnnotationCount],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> list[AttributeValueKey]:
        basic_columns = [
            ("task_id", "", ""),
            ("task_status", "", ""),
            ("task_phase", "", ""),
            ("task_phase_stage", "", ""),
            ("input_data_id", "", ""),
            ("input_data_name", "", ""),
        ]
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns)
        return basic_columns + value_columns

    def create_df(
        self,
        annotation_count_list: list[AnnotationCount],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> pandas.DataFrame:
        def to_cell(c: AnnotationCount) -> dict[tuple[str, str, str], Any]:
            cell: dict[AttributeValueKey, Any] = {
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.status.value,
                ("task_phase", "", ""): c.phase.value,
                ("task_phase_stage", "", ""): c.phase_stage,
            }
            cell.update(c.annotation_attribute_counts)

            return cell

        columns = self.get_columns(annotation_count_list, prior_attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in annotation_count_list], columns=pandas.MultiIndex.from_tuples(columns))

        # アノテーション数の列のNaNを0に変換する
        value_columns = self._value_columns(annotation_count_list, prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df


class ListAnnotationAttributeFilledCountMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def print_annotation_count_csv(
        self, annotation_count_list: list[AnnotationCount], output_file: Path, *, annotation_specs: Optional[AnnotationSpecs]
    ) -> None:
        # TODO 見直す
        # attribute_columns: Optional[list[AttributeValueKey]] = None
        # if annotation_specs is not None:
        #     attribute_columns = annotation_specs.selective_attribute_value_keys()

        # df = AnnotationCountCsvByAttribute().create_df(annotation_count_list, prior_attribute_columns=attribute_columns)
        df = AnnotationCountCsvByAttribute().create_df(annotation_count_list)
        print_csv(df, output_file)

    def print_annotation_count(
        self,
        annotation_path: Path,
        output_file: Path,
        output_format: FormatArgument,
        *,
        project_id: Optional[str] = None,
        input_data_json_path: Optional[Path] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id, annotation_type=DefaultAnnotationType.RANGE.value)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        annotation_count_list = ListAnnotationCountByInputData(
            non_target_attribute_names=non_selective_attribute_name_keys
        ).get_annotation_count_list(
            annotation_path,
            input_data_json_path=input_data_json_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        logger.info(f"{len(annotation_count_list)} 件のタスクに含まれるアノテーション数を出力します。")

        if output_format == FormatArgument.CSV:
            self.print_annotation_count_csv(annotation_count_list, output_file=output_file, annotation_specs=annotation_specs)

        elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
            json_is_pretty = output_format == FormatArgument.PRETTY_JSON

            print_json(
                [e.to_dict(encode_json=True) for e in annotation_count_list],
                is_pretty=json_is_pretty,
                output=output_file,
            )


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
            if project_id is not None:
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
                arg_format=output_format,
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
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",  # noqa: E501
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_attribute_filled_count"
    subcommand_help = "各属性に対して値が空である場合と空でない場合のアノテーションの個数を、タスクごとまたは入力データごとに集計します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
