from __future__ import annotations

import abc
import argparse
import collections
import logging
import tempfile
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Collection, Counter, Iterator, Optional, Tuple

import annofabapi
import pandas
from annofabapi.models import AdditionalDataDefinitionType, TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip,
    lazy_parse_simple_annotation_zip_by_task,
)
from dataclasses_json import DataClassJsonMixin

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import (
    TaskQuery,
    convert_annotation_specs_labels_v2_to_v1,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv
from annofabcli.common.visualize import AddProps, MessageLocale

logger = logging.getLogger(__name__)

AttributesKey = Tuple[str, str, str]
"""
属性のキー.
Tuplelabel_name_en, attribute_name_en, attribute_value] で表す。
"""

LabelKeys = Collection[str]

AttributeKeys = Collection[Collection]


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


@dataclass(frozen=True)
class AnnotationCounter(abc.ABC):
    labels_counter: Counter[str]
    attributes_counter: Counter[AttributesKey]


@dataclass(frozen=True)
class AnnotationCounterByTask(AnnotationCounter, DataClassJsonMixin):

    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    input_data_count: int


@dataclass(frozen=True)
class AnnotationCounterByInputData(AnnotationCounter, DataClassJsonMixin):
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str


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
    """入力データ単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。"""

    @classmethod
    def get_annotation_counter(
        cls,
        simple_annotation: dict[str, Any],
        *,
        target_labels: Optional[Collection[str]] = None,
        target_attributes: Optional[Collection[AttributesKey]] = None,
    ) -> AnnotationCounterByInputData:
        """
        1個の入力データに対して、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
            target_labels: 集計対象のラベル（label_name_en）
            target_attributes: 集計対象の属性（tuplelabel_name_en, attribute_name_en]


        """
        details = simple_annotation["details"]

        labels_counter = collections.Counter([e["label"] for e in details])
        if target_labels is not None:
            labels_counter = collections.Counter({k: v for k, v in labels_counter.items() if k in target_labels})

        attributes_list = []
        for detail in details:
            label = detail["label"]
            for attribute, value in detail["attributes"].items():
                attributes_list.append((label, attribute, str(value)))

        attributes_counter = collections.Counter(attributes_list)
        if target_attributes is not None:
            attributes_counter = collections.Counter(
                {key: count for key, count in attributes_counter.items() if key in target_attributes}
            )

        return AnnotationCounterByInputData(
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            labels_counter=labels_counter,
            attributes_counter=attributes_counter,
        )

    @classmethod
    def get_annotation_counter_list(
        cls,
        annotation_path: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        target_labels: Optional[Collection[str]] = None,
        target_attributes: Optional[Collection[AttributesKey]] = None,
    ) -> list[AnnotationCounterByInputData]:
        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
            target_labels: 集計対象のラベル（label_name_en）
            target_attributes: 集計対象の属性（tuplelabel_name_en, attribute_name_en]


        """

        counter_list = []

        target_labels = set(target_labels) if target_labels is not None else None
        target_attributes = set(target_attributes) if target_attributes is not None else None
        target_task_ids = set(target_task_ids) if target_task_ids is not None else None

        iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)

        logger.debug(f"アノテーションzip/ディレクトリを読み込み中")
        for index, parser in enumerate(iter_parser):
            if (index + 1) % 1000 == 0:
                logger.debug(f"{index+1}  件目のJSONを読み込み中")

            if target_task_ids is not None and parser.task_id not in target_task_ids:
                continue

            simple_annotation_dict = parser.load_json()
            if task_query is not None:
                if not match_annotation_with_task_query(simple_annotation_dict, task_query):
                    continue

            input_data_counter = cls.get_annotation_counter(
                simple_annotation_dict, target_labels=target_labels, target_attributes=target_attributes
            )
            counter_list.append(input_data_counter)

        return counter_list

    @classmethod
    def print_labels_count(
        cls,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        label_columns: Optional[list[str]] = None,
        csv_format: Optional[dict[str, Any]] = None,
    ):
        def to_dict(c: AnnotationCounterByInputData) -> dict[str, Any]:
            d = {
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
            }
            d.update(c.labels_counter)
            return d

        basic_columns = ["input_data_id", "input_data_name", "task_id", "task_status", "task_phase", "task_phase_stage"]
        if label_columns is not None:
            value_columns = label_columns
        else:
            label_column_set = {label for c in counter_list for label in c.labels_counter}
            value_columns = sorted(list(label_column_set))

        columns = basic_columns + value_columns
        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=columns)

        # NaNを0に変換する
        df.fillna({e: 0 for e in value_columns}, inplace=True)

        print_csv(df, output=str(output_file), to_csv_kwargs=csv_format)

    @classmethod
    def print_attributes_count(
        cls,
        counter_list: list[AnnotationCounterByInputData],
        output_file: Path,
        attribute_columns: Optional[list[AttributesKey]] = None,
        csv_format: Optional[dict[str, Any]] = None,
    ):
        def to_cell(c: AnnotationCounterByInputData) -> dict[tuple[str, str, str], Any]:
            cell = {
                ("", "", "input_data_id"): c.input_data_id,
                ("", "", "input_data_name"): c.input_data_name,
                ("", "", "task_id"): c.task_id,
                ("", "", "task_status"): c.task_status.value,
                ("", "", "task_phase"): c.task_phase.value,
                ("", "", "task_phase_stage"): c.task_phase_stage,
            }
            cell.update(c.attributes_counter)

            return cell

        basic_columns = [
            ("", "", "input_data_id"),
            ("", "", "input_data_name"),
            ("", "", "task_id"),
            ("", "", "task_status"),
            ("", "", "task_phase"),
            ("", "", "task_phase_stage"),
        ]

        if attribute_columns is not None:
            value_columns = attribute_columns
        else:
            attr_key_set = {attr_key for c in counter_list for attr_key in c.attributes_counter}
            value_columns = sorted(list(attr_key_set))

        columns = basic_columns + value_columns
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # NaNを0に変換する
        df.fillna({e: 0 for e in value_columns}, inplace=True)

        print_csv(df, output=str(output_file), to_csv_kwargs=csv_format)


class ListAnnotationCounterByTask:
    """タスク単位で、ラベルごと/属性ごとのアノテーション数を集計情報を取得するメソッドの集まり。"""

    @staticmethod
    def get_annotation_counter(
        task_parser: SimpleAnnotationParserByTask,
        target_labels: Optional[Collection[str]] = None,
        target_attributes: Optional[Collection[AttributesKey]] = None,
    ) -> AnnotationCounterByTask:
        """
        1個のタスクに対して、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
            target_labels: 集計対象のラベル（label_name_en）
            target_attributes: 集計対象の属性（tuplelabel_name_en, attribute_name_en]


        """

        labels_counter: Counter[str] = collections.Counter()
        attributes_counter: Counter[Tuple[str, str, str]] = collections.Counter()

        last_simple_annotation = None
        input_data_count = 0
        for parser in task_parser.lazy_parse():
            # parse()メソッドは遅いので、使わない
            simple_annotation_dict = parser.load_json()
            input_data = ListAnnotationCounterByInputData.get_annotation_counter(
                simple_annotation_dict, target_labels=target_labels, target_attributes=target_attributes
            )
            labels_counter += input_data.labels_counter
            attributes_counter += input_data.attributes_counter
            last_simple_annotation = simple_annotation_dict
            input_data_count += 1

        if last_simple_annotation is None:
            raise RuntimeError(f"{task_parser.task_id} ディレクトリにはjsonファイルが１つも含まれていません。")

        return AnnotationCounterByTask(
            task_id=last_simple_annotation["task_id"],
            task_status=TaskStatus(last_simple_annotation["task_status"]),
            task_phase=TaskPhase(last_simple_annotation["task_phase"]),
            task_phase_stage=last_simple_annotation["task_phase_stage"],
            input_data_count=input_data_count,
            labels_counter=labels_counter,
            attributes_counter=attributes_counter,
        )

    @classmethod
    def get_annotation_counter_list(
        cls,
        annotation_path: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        target_labels: Optional[Collection[str]] = None,
        target_attributes: Optional[Collection[AttributesKey]] = None,
    ) -> list[AnnotationCounterByTask]:

        """
        アノテーションzipまたはそれを展開したディレクトリから、ラベルごと/属性ごとのアノテーション数を集計情報を取得する。

        Args:
            simple_annotation: JSONファイルの内容
            target_labels: 集計対象のラベル（label_name_en）
            target_attributes: 集計対象の属性（tuplelabel_name_en, attribute_name_en]


        """

        counter_list = []
        iter_task_parser = lazy_parse_simple_annotation_by_task(annotation_path)

        target_labels = set(target_labels) if target_labels is not None else None
        target_attributes = set(target_attributes) if target_attributes is not None else None
        target_task_ids = set(target_task_ids) if target_task_ids is not None else None

        logger.debug(f"アノテーションzip/ディレクトリを読み込み中")
        for task_index, task_parser in enumerate(iter_task_parser):
            if (task_index + 1) % 1000 == 0:
                logger.debug(f"{task_index+1}  件目のタスクディレクトリを読み込み中")

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

            task_counter = cls.get_annotation_counter(
                task_parser, target_labels=target_labels, target_attributes=target_attributes
            )
            counter_list.append(task_counter)

        return counter_list

    @classmethod
    def print_labels_count(
        cls,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        label_columns: Optional[list[str]] = None,
        csv_format: Optional[dict[str, Any]] = None,
    ):
        def to_dict(c: AnnotationCounterByTask) -> dict[str, Any]:
            d = {
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "input_data_count": c.input_data_count,
            }
            d.update(c.labels_counter)
            return d

        basic_columns = ["task_id", "task_status", "task_phase", "task_phase_stage", "input_data_count"]
        if label_columns is not None:
            value_columns = label_columns
        else:
            label_column_set = {label for c in counter_list for label in c.labels_counter}
            value_columns = sorted(list(label_column_set))

        columns = basic_columns + value_columns
        df = pandas.DataFrame([to_dict(e) for e in counter_list], columns=columns)

        # NaNを0に変換する
        df.fillna({e: 0 for e in value_columns}, inplace=True)

        print_csv(df, output=str(output_file), to_csv_kwargs=csv_format)

    @classmethod
    def print_attributes_count(
        cls,
        counter_list: list[AnnotationCounterByTask],
        output_file: Path,
        attribute_columns: Optional[list[AttributesKey]] = None,
        csv_format: Optional[dict[str, Any]] = None,
    ):
        def to_cell(c: AnnotationCounterByTask) -> dict[AttributesKey, Any]:
            cell = {
                ("", "", "task_id"): c.task_id,
                ("", "", "task_status"): c.task_status.value,
                ("", "", "task_phase"): c.task_phase.value,
                ("", "", "task_phase_stage"): c.task_phase_stage,
                ("", "", "input_data_count"): c.input_data_count,
            }
            cell.update(c.attributes_counter)
            return cell

        # if len(attribute_columns) == 0:
        #     logger.warning(f"アノテーション仕様に集計対象の属性が定義されていないため、'{output_file}' は出力しません。")
        #     return

        basic_columns = [
            ("", "", "task_id"),
            ("", "", "task_status"),
            ("", "", "task_phase"),
            ("", "", "task_phase_stage"),
            ("", "", "input_data_count"),
        ]

        if attribute_columns is not None:
            value_columns = attribute_columns
        else:
            attr_key_set = {attr_key for c in counter_list for attr_key in c.attributes_counter}
            value_columns = sorted(list(attr_key_set))

        columns = basic_columns + value_columns
        df = pandas.DataFrame([to_cell(e) for e in counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        # NaNを0に変換する
        df.fillna({e: 0 for e in value_columns}, inplace=True)

        print_csv(df, output=str(output_file), to_csv_kwargs=csv_format)


class ListAnnotationCountMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def _get_target_attributes_columns(annotation_specs_labels: list[dict[str, Any]]) -> list[AttributesKey]:
        """
        出力対象の属性情報を取得する（label, attribute, choice)
        """

        target_attributes_columns = []
        for label in annotation_specs_labels:
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
                        target_attributes_columns.append((label_name_en, attribute_name_en, choice_name_en))

                elif AdditionalDataDefinitionType(attribute["type"]) == AdditionalDataDefinitionType.FLAG:
                    target_attributes_columns.append((label_name_en, attribute_name_en, "True"))
                    target_attributes_columns.append((label_name_en, attribute_name_en, "False"))

                else:
                    continue

        return target_attributes_columns

    @staticmethod
    def _get_target_label_columns(annotation_specs_labels: list[dict[str, Any]]) -> list[str]:
        """
        出力対象の属性情報を取得する（label, attribute, choice)
        """

        def to_label_name(label: dict[str, Any]) -> str:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""
            return label_name_en

        return [to_label_name(label) for label in annotation_specs_labels]

    def get_target_columns(self, project_id: str) -> tuple[list[str], list[AttributesKey]]:
        """
        出力対象のラベルと属性の一覧を取得します。

        集計対象の属性の種類は以下の通りです。
         * ドロップダウン
         * ラジオボタン
         * チェックボックス

        Args:
            project_id (str): [description]

        Returns:
            tuple0] : 出力対象ラベルの一覧。list[label_name_en]
            tuple1] : 出力対象属性の一覧。list[tuplelabel_name_en, attribute_name_en, attribute_value].
        """
        # [REMOVE_V2_PARAM]
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        labels_v1 = convert_annotation_specs_labels_v2_to_v1(
            labels_v2=annotation_specs["labels"], additionals_v2=annotation_specs["additionals"]
        )
        label_columns = self._get_target_label_columns(labels_v1)
        attributes_columns = self._get_target_attributes_columns(labels_v1)
        return (label_columns, attributes_columns)

    def print_annotation_counter_csv(
        self,
        project_id: str,
        annotation_path: Path,
        group_by: GroupBy,
        output_dir: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ):

        labels_count_csv = output_dir / "labels_count.csv"
        attributes_count_csv = output_dir / "attributes_count.csv"

        # 集計対象の属性を、選択肢系の属性にする
        label_columns, attribute_columns = self.get_target_columns(project_id)
        if len(attribute_columns) == 0:
            logger.info(f"アノテーション仕様に集計対象の属性が定義されていないため、{attributes_count_csv} は出力しません。")

        if group_by == GroupBy.INPUT_DATA_ID:
            counter_list_by_input_data = ListAnnotationCounterByInputData.get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_attributes=attribute_columns,
            )

            ListAnnotationCounterByInputData.print_labels_count(
                counter_list_by_input_data, labels_count_csv, label_columns=label_columns
            )

            if len(attribute_columns) > 0:
                ListAnnotationCounterByInputData.print_attributes_count(
                    counter_list_by_input_data, attributes_count_csv, attribute_columns=attribute_columns
                )

        elif group_by == GroupBy.TASK_ID:
            counter_list_by_task = ListAnnotationCounterByTask.get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_attributes=attribute_columns,
            )

            ListAnnotationCounterByTask.print_labels_count(
                counter_list_by_task, labels_count_csv, label_columns=label_columns
            )

            if len(attribute_columns) > 0:
                ListAnnotationCounterByTask.print_attributes_count(
                    counter_list_by_task, attributes_count_csv, attribute_columns=attribute_columns
                )

        else:
            raise RuntimeError(f"group_by='{group_by}'が対象外です。")


class ListAnnotationCount(AbstractCommandLineInterface):
    """
    アノテーション数情報を出力する。
    """

    def main(self):
        args = self.args

        project_id = args.project_id
        output_dir: Path = args.output_dir
        super().validate_project(project_id, project_member_roles=None)

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        group_by = GroupBy(args.group_by)

        main_obj = ListAnnotationCountMain(self.service)

        if annotation_path is None:
            with tempfile.NamedTemporaryFile() as f:
                annotation_path = Path(f.name)
                downloading_obj = DownloadingFile(self.service)
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=str(annotation_path),
                    is_latest=args.latest,
                )
                main_obj.print_annotation_counter_csv(
                    project_id=project_id,
                    annotation_path=annotation_path,
                    group_by=group_by,
                    output_dir=output_dir,
                    target_task_ids=task_id_list,
                    task_query=task_query,
                )
        else:
            main_obj.print_annotation_counter_csv(
                project_id=project_id,
                annotation_path=annotation_path,
                group_by=group_by,
                output_dir=output_dir,
                target_task_ids=task_id_list,
                task_query=task_query,
            )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--annotation", type=str, help="アノテーションzip、またはzipを展開したディレクトリを指定します。" "指定しない場合はAnnoFabからダウンロードします。"
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。デフォルトは'task_id'です。",
    )

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
        help="'--annotation'を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="アノテーションzipの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        " ``file://`` を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは ``{"interval":60, "max_tries":360}`` です。'
        "``interval`` :完了したかを問い合わせる間隔[秒], "
        "``max_tires`` :完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_annotation_count"
    subcommand_help = "各ラベル、各属性値のアノテーション数を出力します。"
    description = "各ラベル、各属性値のアノテーション数を、タスクごと/入力データごとに出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
