import argparse
import collections
import logging
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Counter, Dict, Iterator, List, Optional, Set, Tuple

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
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import (
    TaskQuery,
    convert_annotation_specs_labels_v2_to_v1,
    match_annotation_with_task_query,
)
from annofabcli.common.visualize import AddProps, MessageLocale

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)

logger = logging.getLogger(__name__)

AttributesColumn = Tuple[str, str, str]
"""
属性値ごとの個数を表したCSVの列の型
Tuple[Label, Attribute, Choice]
"""

LabelColumnList = List[str]

AttributesColumnList = List[AttributesColumn]


class GroupBy(Enum):
    TASK_ID = "task_id"
    INPUT_DATA_ID = "input_data_id"


@dataclass(frozen=True)
class AnnotationCounterByTask(DataClassJsonMixin):
    """"""

    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    input_data_count: int
    labels_count: Counter[str]
    attributes_count: Counter[AttributesColumn]


@dataclass(frozen=True)
class AnnotationCounterByInputData(DataClassJsonMixin):
    """"""

    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    labels_count: Counter[str]
    attributes_count: Counter[AttributesColumn]


class ListAnnotationCount(AbstractCommandLineInterface):
    """
    アノテーション数情報を出力する。
    """

    CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}
    ATTRIBUTES_COUNT_CSV = "attributes_count.csv"
    LABELS_COUNT_CSV = "labels_count.csv"

    @staticmethod
    def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
        if not annotation_path.exists():
            raise RuntimeError("'--annotation'で指定したディレクトリまたはファイルが存在しません。")

        if annotation_path.is_dir():
            return lazy_parse_simple_annotation_dir(annotation_path)
        elif zipfile.is_zipfile(str(annotation_path)):
            return lazy_parse_simple_annotation_zip(annotation_path)
        else:
            raise RuntimeError(f"'--annotation'で指定した'{annotation_path}'は、zipファイルまたはディレクトリではありませんでした。")

    @staticmethod
    def lazy_parse_simple_annotation_by_task(annotation_path: Path) -> Iterator[SimpleAnnotationParserByTask]:
        if not annotation_path.exists():
            raise RuntimeError("'--annotation'で指定したディレクトリまたはファイルが存在しません。")

        if annotation_path.is_dir():
            return lazy_parse_simple_annotation_dir_by_task(annotation_path)
        elif zipfile.is_zipfile(str(annotation_path)):
            return lazy_parse_simple_annotation_zip_by_task(annotation_path)
        else:
            raise RuntimeError(f"'--annotation'で指定した'{annotation_path}'は、zipファイルまたはディレクトリではありませんでした。")

    @staticmethod
    def count_for_input_data(
        simple_annotation: Dict[str, Any], target_attributes: Optional[Set[Tuple[str, str]]] = None
    ) -> AnnotationCounterByInputData:
        """
        1個の入力データに対してアノテーション数をカウントする

        Args:
            simple_annotation: JSONファイルの内容
            target_attributes:

        Returns:

        """
        details = simple_annotation["details"]
        labels_count = collections.Counter([e["label"] for e in details])

        attributes_list: List[Tuple[str, str, str]] = []
        for detail in details:
            label = detail["label"]
            for attribute, value in detail["attributes"].items():
                if target_attributes is not None and (label, attribute) in target_attributes:
                    attributes_list.append((label, attribute, str(value)))

        attributes_count = collections.Counter(attributes_list)

        return AnnotationCounterByInputData(
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            labels_count=labels_count,
            attributes_count=attributes_count,
        )

    @staticmethod
    def count_for_task(
        task_parser: SimpleAnnotationParserByTask, target_attributes: Optional[Set[Tuple[str, str]]] = None
    ) -> AnnotationCounterByTask:
        """
        1個のタスクに対してアノテーション数をカウントする

        """

        labels_count: Counter[str] = collections.Counter()
        attributes_count: Counter[Tuple[str, str, str]] = collections.Counter()

        last_simple_annotation = None
        input_data_count = 0
        for parser in task_parser.lazy_parse():
            # parse()メソッドは遅いので、使わない
            simple_annotation_dict = parser.load_json()
            input_data = ListAnnotationCount.count_for_input_data(simple_annotation_dict, target_attributes)
            labels_count += input_data.labels_count
            attributes_count += input_data.attributes_count
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
            labels_count=labels_count,
            attributes_count=attributes_count,
        )

    def print_labels_count_for_task(
        self, task_counter_list: List[AnnotationCounterByTask], label_columns: List[str], output_dir: Path
    ):
        def to_dict(c: AnnotationCounterByTask) -> Dict[str, Any]:
            d = {
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "input_data_count": c.input_data_count,
            }
            d.update({f"label_{label}": c.labels_count[label] for label in label_columns})
            return d

        columns = ["task_id", "task_status", "task_phase", "task_phase_stage", "input_data_count"]
        columns.extend([f"label_{e}" for e in label_columns])

        df = pandas.DataFrame([to_dict(e) for e in task_counter_list], columns=columns)
        output_file = str(output_dir / self.LABELS_COUNT_CSV)
        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    def print_attributes_count_for_task(
        self,
        task_counter_list: List[AnnotationCounterByTask],
        attribute_columns: List[Tuple[str, str, str]],
        output_dir: Path,
    ):
        def to_cell(c: AnnotationCounterByTask) -> Dict[AttributesColumn, Any]:
            cell = {
                ("", "", "task_id"): c.task_id,
                ("", "", "task_status"): c.task_status.value,
                ("", "", "task_phase"): c.task_phase.value,
                ("", "", "task_phase_stage"): c.task_phase_stage,
                ("", "", "input_data_count"): c.input_data_count,
            }
            for col in attribute_columns:
                cell.update({col: c.attributes_count[col]})

            return cell

        output_file = str(output_dir / self.ATTRIBUTES_COUNT_CSV)
        if len(attribute_columns) == 0:
            logger.warning(f"アノテーション仕様に集計対象の属性が定義されていないため、'{output_file}' は出力しません。")
            return

        columns = [
            ("", "", "task_id"),
            ("", "", "task_status"),
            ("", "", "task_phase"),
            ("", "", "task_phase_stage"),
            ("", "", "input_data_count"),
        ]
        columns.extend(attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in task_counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    def print_labels_count_for_input_data(
        self, input_data_counter_list: List[AnnotationCounterByInputData], label_columns: List[str], output_dir: Path
    ):
        def to_dict(c: AnnotationCounterByInputData) -> Dict[str, Any]:
            d = {
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
            }
            d.update({f"label_{label}": c.labels_count[label] for label in label_columns})
            return d

        columns = ["input_data_id", "input_data_name", "task_id", "task_status", "task_phase", "task_phase_stage"]
        columns.extend([f"label_{e}" for e in label_columns])

        df = pandas.DataFrame([to_dict(e) for e in input_data_counter_list])
        output_file = str(output_dir / self.LABELS_COUNT_CSV)
        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    def print_attributes_count_for_input_data(
        self,
        input_data_counter_list: List[AnnotationCounterByInputData],
        attribute_columns: List[Tuple[str, str, str]],
        output_dir: Path,
    ):
        def to_cell(c: AnnotationCounterByInputData) -> Dict[AttributesColumn, Any]:
            cell = {
                ("", "", "input_data_id"): c.input_data_id,
                ("", "", "input_data_name"): c.input_data_name,
                ("", "", "task_id"): c.task_id,
                ("", "", "task_status"): c.task_status.value,
                ("", "", "task_phase"): c.task_phase.value,
                ("", "", "task_phase_stage"): c.task_phase_stage,
            }
            for col in attribute_columns:
                cell.update({col: c.attributes_count[col]})

            return cell

        output_file = str(output_dir / self.ATTRIBUTES_COUNT_CSV)
        if len(attribute_columns) == 0:
            logger.warning(f"アノテーション仕様に集計対象の属性が定義されていないため、'{output_file}' は出力しません。")
            return

        columns = [
            ("", "", "input_data_id"),
            ("", "", "input_data_name"),
            ("", "", "task_id"),
            ("", "", "task_status"),
            ("", "", "task_phase"),
            ("", "", "task_phase_stage"),
        ]
        columns.extend(attribute_columns)
        df = pandas.DataFrame(
            [to_cell(e) for e in input_data_counter_list], columns=pandas.MultiIndex.from_tuples(columns)
        )
        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    @staticmethod
    def get_target_attributes_columns(annotation_specs_labels: List[Dict[str, Any]]) -> List[AttributesColumn]:
        """
        出力対象の属性情報を取得する（label, attribute, choice)
        """

        target_attributes_columns: List[AttributesColumn] = []
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
    def get_target_label_columns(annotation_specs_labels: List[Dict[str, Any]]) -> List[str]:
        """
        出力対象の属性情報を取得する（label, attribute, choice)
        """

        def to_label_name(label: Dict[str, Any]) -> str:
            label_name_en = AddProps.get_message(label["label_name"], MessageLocale.EN)
            label_name_en = label_name_en if label_name_en is not None else ""
            return label_name_en

        return [to_label_name(label) for label in annotation_specs_labels]

    def get_target_columns(self, project_id: str) -> Tuple[LabelColumnList, AttributesColumnList]:
        # [REMOVE_V2_PARAM]
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        labels_v1 = convert_annotation_specs_labels_v2_to_v1(
            labels_v2=annotation_specs["labels"], additionals_v2=annotation_specs["additionals"]
        )
        label_columns = self.get_target_label_columns(labels_v1)
        attributes_columns = self.get_target_attributes_columns(labels_v1)
        return (label_columns, attributes_columns)

    def list_annotation_count_by_task(
        self,
        project_id: str,
        annotation_path: Path,
        output_dir: Path,
        task_id_set: Optional[Set[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        task_counter_list = []
        iter_task_parser = self.lazy_parse_simple_annotation_by_task(annotation_path)
        target_label_columns, target_attributes_columns = self.get_target_columns(project_id)

        target_attributes = {(e[0], e[1]) for e in target_attributes_columns}
        logger.info(f"アノテーションzip/ディレクトリを読み込み中")
        for task_index, task_parser in enumerate(iter_task_parser):
            if (task_index + 1) % 1000 == 0:
                logger.debug(f"{task_index+1}  件目のタスクディレクトリを読み込み中")

            if task_id_set is not None and task_parser.task_id not in task_id_set:
                continue

            if task_query is not None:
                json_file_path_list = task_parser.json_file_path_list
                if len(json_file_path_list) == 0:
                    continue
                input_data_parser = task_parser.get_parser(json_file_path_list[0])
                dict_simple_annotation = input_data_parser.load_json()
                if not match_annotation_with_task_query(dict_simple_annotation, task_query):
                    continue

            task_counter = self.count_for_task(task_parser, target_attributes=target_attributes)
            task_counter_list.append(task_counter)

        self.print_labels_count_for_task(task_counter_list, label_columns=target_label_columns, output_dir=output_dir)

        self.print_attributes_count_for_task(
            task_counter_list,
            output_dir=output_dir,
            attribute_columns=target_attributes_columns,
        )

    def list_annotation_count_by_input_data(
        self,
        project_id: str,
        annotation_path: Path,
        output_dir: Path,
        task_id_set: Optional[Set[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> None:
        input_data_counter_list = []
        iter_parser = self.lazy_parse_simple_annotation_by_input_data(annotation_path)
        target_label_columns, target_attributes_columns = self.get_target_columns(project_id)

        target_attributes = {(e[0], e[1]) for e in target_attributes_columns}
        logger.info(f"アノテーションzip/ディレクトリを読み込み中")
        for index, parser in enumerate(iter_parser):
            if (index + 1) % 1000 == 0:
                logger.debug(f"{index+1}  件目のJSONを読み込み中")

            if task_id_set is not None and parser.task_id not in task_id_set:
                continue

            simple_annotation_dict = parser.load_json()
            if task_query is not None:
                if not match_annotation_with_task_query(simple_annotation_dict, task_query):
                    continue

            input_data_counter = self.count_for_input_data(simple_annotation_dict, target_attributes=target_attributes)
            input_data_counter_list.append(input_data_counter)

        self.print_labels_count_for_input_data(
            input_data_counter_list, label_columns=target_label_columns, output_dir=output_dir
        )

        self.print_attributes_count_for_input_data(
            input_data_counter_list,
            output_dir=output_dir,
            attribute_columns=target_attributes_columns,
        )

    def main(self):
        args = self.args

        project_id = args.project_id
        super().validate_project(project_id, project_member_roles=None)

        if args.annotation is not None:
            annotation_path = Path(args.annotation)
        else:
            cache_dir = annofabcli.utils.get_cache_dir()
            annotation_path = cache_dir / f"annotation-{project_id}.zip"
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_annotation_zip(
                project_id,
                dest_path=str(annotation_path),
                is_latest=args.latest,
                wait_options=wait_options,
            )

        task_id_set = set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        group_by = GroupBy(args.group_by)
        if group_by == GroupBy.TASK_ID:
            self.list_annotation_count_by_task(
                project_id,
                annotation_path=annotation_path,
                output_dir=Path(args.output_dir),
                task_id_set=task_id_set,
                task_query=task_query,
            )
        elif group_by == GroupBy.INPUT_DATA_ID:
            self.list_annotation_count_by_input_data(
                project_id,
                annotation_path=annotation_path,
                output_dir=Path(args.output_dir),
                task_id_set=task_id_set,
                task_query=task_query,
            )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--annotation", type=str, help="アノテーションzip、またはzipを展開したディレクトリを指定します。" "指定しない場合はAnnoFabからダウンロードします。"
    )
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

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
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
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
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_annotation_count"
    subcommand_help = "各ラベル、各属性値のアノテーション数を出力します。"
    description = "各ラベル、各属性値のアノテーション数を、タスクごと/入力データごとに出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
