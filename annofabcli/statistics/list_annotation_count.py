import argparse
import collections
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Counter, Dict, Iterator, List, Optional, Set, Tuple

import pandas
from annofabapi.dataclass.annotation import SimpleAnnotation
from annofabapi.models import AdditionalDataDefinitionType, TaskPhase, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationParser,
    SimpleAnnotationParserByTask,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_dir_by_task,
    lazy_parse_simple_annotation_zip,
    lazy_parse_simple_annotation_zip_by_task,
)
from dataclasses_json import dataclass_json

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.visualize import AddProps, MessageLocale

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass(frozen=True)
class AnnotationCounterByTask:
    """

    """

    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int
    labels_count: Counter[str]
    attirbutes_count: Counter[Tuple[str, str, str]]


@dataclass_json
@dataclass(frozen=True)
class AnnotationCounterByInputData:
    """

    """

    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str
    labels_count: Counter[str]
    attirbutes_count: Counter[Tuple[str, str, str]]


class ListAnnotationCount(AbstractCommandLineInterface):
    """
    アノテーション数情報を出力する。
    """

    CSV_FORMAT = {"encoding": "utf_8_sig", "index": False}

    @staticmethod
    def lazy_parse_simple_annotation(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
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

    def count_for_input_data(
        self, simple_annotation: SimpleAnnotation, target_attributes: Optional[Set[Tuple[str, str]]] = None
    ) -> AnnotationCounterByInputData:
        """
        1個の入力データに対してアノテーション数をカウントする

        Args:
            simple_annotation: JSONファイルの内容
            target_attributes:

        Returns:

        """

        labels_count = collections.Counter([e.label for e in simple_annotation.details])

        attributes_list: List[Tuple[str, str, str]] = []
        for detail in simple_annotation.details:
            label = detail.label
            for attribute, value in detail.attributes.items():
                if target_attributes is not None and (label, attribute) in target_attributes:
                    attributes_list.append((label, attribute, str(value)))

        attirbutes_count = collections.Counter(attributes_list)

        return AnnotationCounterByInputData(
            task_id=simple_annotation.task_id,
            task_phase=simple_annotation.task_phase,
            task_phase_stage=simple_annotation.task_phase_stage,
            task_status=simple_annotation.task_status,
            input_data_id=simple_annotation.input_data_id,
            input_data_name=simple_annotation.input_data_name,
            labels_count=labels_count,
            attirbutes_count=attirbutes_count,
        )

    def count_for_task(
        self, task_parser: SimpleAnnotationParserByTask, target_attributes: Optional[Set[Tuple[str, str]]] = None
    ) -> AnnotationCounterByTask:
        """
        1個のタスクに対してアノテーション数をカウントする

        """

        labels_count: Counter[str] = collections.Counter()
        attirbutes_count: Counter[Tuple[str, str, str]] = collections.Counter()

        last_simple_annotation = None
        for parser in task_parser.lazy_parse():
            simple_annotation = parser.parse()
            input_data = self.count_for_input_data(simple_annotation, target_attributes)
            labels_count += input_data.labels_count
            attirbutes_count += input_data.attirbutes_count
            last_simple_annotation = simple_annotation

        if last_simple_annotation is None:
            raise RuntimeError(f"{task_parser.task_id} ディレクトリにはjsonファイルが１つも含まれていません。")

        return AnnotationCounterByTask(
            task_id=last_simple_annotation.task_id,
            task_status=last_simple_annotation.task_status,
            task_phase=last_simple_annotation.task_phase,
            task_phase_stage=last_simple_annotation.task_phase_stage,
            labels_count=labels_count,
            attirbutes_count=attirbutes_count,
        )

    def print_labels_count(self, task_counter_list: List[AnnotationCounterByTask], output_dir: Path):
        def to_dict(c: AnnotationCounterByTask) -> Dict[str, Any]:
            d = {
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
            }
            d.update({f"label_{label}": count for label, count in c.labels_count.items()})
            return d

        df = pandas.DataFrame([to_dict(e) for e in task_counter_list])
        output_file = str(output_dir / "labels_count.csv")
        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    def print_attirbutes_count(
        self,
        task_counter_list: List[AnnotationCounterByTask],
        attribute_columns: List[Tuple[str, str, str]],
        output_dir: Path,
    ):
        def to_cell(c: AnnotationCounterByTask) -> Dict[Tuple[str,str,str], Any]:
            cell = {
                ("", "", "task_id"): c.task_id,
                ("", "", "task_status"): c.task_status.value,
                ("", "", "task_phase"): c.task_phase.value,
                ("", "", "task_phase_stage"): c.task_phase_stage,
            }
            for col in attribute_columns:
                cell.update({col: c.attirbutes_count[col]})

            return cell

        columns = [("", "", "task_id"), ("", "", "task_status"), ("", "", "task_phase"), ("", "", "task_phase_stage")]
        columns.extend(attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in task_counter_list], columns=pandas.MultiIndex.from_tuples(columns))

        output_file = str(output_dir / "attirbutes_count.csv")
        annofabcli.utils.print_csv(df, output=output_file, to_csv_kwargs=self.CSV_FORMAT)

    def get_target_attributes_columns(self, project_id: str) -> List[Tuple[str, str, str]]:
        """
        出力対象の属性情報を取得する（label, attribute, choice)

        """
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        annotation_specs_labels = annotation_specs["labels"]

        target_attributes_columns: List[Tuple[str, str, str]] = []
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

    def list_annotation_count_by_task(self, project_id: str, annotation_path: Path, output_dir: Path) -> None:
        super().validate_project(project_id, project_member_roles=None)

        task_counter_list = []
        iter_task_parser = self.lazy_parse_simple_annotation_by_task(annotation_path)
        target_attributes_columns = self.get_target_attributes_columns(project_id)

        target_attributes = {(e[0], e[1]) for e in target_attributes_columns}
        for task_parser in iter_task_parser:
            task_counter = self.count_for_task(task_parser, target_attributes=target_attributes)
            task_counter_list.append(task_counter)

        self.print_labels_count(task_counter_list, output_dir)

        self.print_attirbutes_count(
            task_counter_list, output_dir=output_dir, attribute_columns=target_attributes_columns,
        )

    def main(self):
        args = self.args

        project_id = args.project_id
        self.list_annotation_count_by_task(
            project_id, annotation_path=Path(args.annotation), output_dir=Path(args.output_dir)
        )


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument("--annotation", type=str, required=True, help="アノテーションzip、またはzipを展開したディレクトリ")
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_annotation_count"
    subcommand_help = "アノテーション数の情報を出力する。"
    description = "アノテーション数の情報を出力する。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
