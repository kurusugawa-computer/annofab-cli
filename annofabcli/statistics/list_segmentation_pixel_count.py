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
from annofabapi.segmentation import read_binary_image
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
LabelKeys = Collection[str]
AttributeNameKey = tuple[str, str]
AttributeKeys = Collection[Collection]

class CsvType(Enum):
    LABEL = "label"
    ATTRIBUTE = "attribute"

def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")

def encode_pixel_count_by_attribute(
    pixel_count_by_attribute: dict[AttributeValueKey, int],
) -> dict[str, dict[str, dict[str, int]]]:
    def _factory() -> collections.defaultdict:
        return collections.defaultdict(_factory)
    result: dict[str, dict[str, dict[str, int]]] = defaultdict(_factory)
    for (label_name, attribute_name, attribute_value), pixel_count in pixel_count_by_attribute.items():
        result[label_name][attribute_name][attribute_value] = pixel_count
    return result

@dataclass(frozen=True)
class AnnotationPixelCount(DataClassJsonMixin):
    task_id: str
    task_status: TaskStatus
    task_phase: TaskPhase
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    pixel_count: int
    pixel_count_by_label: dict[str, int]
    pixel_count_by_attribute: dict[AttributeValueKey, int] = field(
        metadata=config(
            encoder=encode_pixel_count_by_attribute,
        )
    )

class ListSegmentationPixelCountByInputData:
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

    def get_pixel_count(self, simple_annotation: dict[str, Any]) -> AnnotationPixelCount:
        def convert_attribute_value_to_key(value: Union[bool, str, float]) -> str:
            if isinstance(value, bool):
                return "true" if value else "false"
            return str(value)

        # Segmentationアノテーションのみ
        segmentation_details = [e for e in simple_annotation["details"] if e["data"]["_type"] == "Segmentation"]

        pixel_count_by_label: dict[str, int] = defaultdict(int)
        pixel_count_by_attribute: dict[AttributeValueKey, int] = defaultdict(int)

        for detail in segmentation_details:
            label = detail["label"]
            mask_data = detail["data"]["mask"]
            try:
                binary_image = read_binary_image(mask_data)
                count = int(binary_image.sum())
            except Exception as e:
                logger.warning(f"maskデータの読み込みに失敗しました: {e}")
                count = 0

            pixel_count_by_label[label] += count

            for attribute, value in detail["attributes"].items():
                attribute_key = (label, attribute, convert_attribute_value_to_key(value))
                pixel_count_by_attribute[attribute_key] += count

        if self.target_labels is not None:
            pixel_count_by_label = {
                label: cnt for label, cnt in pixel_count_by_label.items() if label in self.target_labels
            }
        if self.non_target_labels is not None:
            pixel_count_by_label = {
                label: cnt for label, cnt in pixel_count_by_label.items() if label not in self.non_target_labels
            }

        if self.target_attribute_names is not None:
            pixel_count_by_attribute = {
                (label, attribute_name, attribute_value): cnt
                for (label, attribute_name, attribute_value), cnt in pixel_count_by_attribute.items()
                if (label, attribute_name) in self.target_attribute_names
            }
        if self.non_target_attribute_names is not None:
            pixel_count_by_attribute = {
                (label, attribute_name, attribute_value): cnt
                for (label, attribute_name, attribute_value), cnt in pixel_count_by_attribute.items()
                if (label, attribute_name) not in self.non_target_attribute_names
            }

        return AnnotationPixelCount(
            task_id=simple_annotation["task_id"],
            task_phase=TaskPhase(simple_annotation["task_phase"]),
            task_phase_stage=simple_annotation["task_phase_stage"],
            task_status=TaskStatus(simple_annotation["task_status"]),
            input_data_id=simple_annotation["input_data_id"],
            input_data_name=simple_annotation["input_data_name"],
            pixel_count=sum(pixel_count_by_label.values()),
            pixel_count_by_label=pixel_count_by_label,
            pixel_count_by_attribute=pixel_count_by_attribute,
        )

    def get_pixel_count_list(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> list[AnnotationPixelCount]:
        pixel_count_list = []
        target_task_ids = set(target_task_ids) if target_task_ids is not None else None
        iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)
        logger.debug("アノテーションzip/ディレクトリを読み込み中")
        for index, parser in enumerate(iter_parser):
            if (index + 1) % 1000 == 0:
                logger.debug(f"{index + 1}  件目のJSONを読み込み中")
            if target_task_ids is not None and parser.task_id not in target_task_ids:
                continue
            simple_annotation_dict = parser.load_json()
            if task_query is not None:
                if not match_annotation_with_task_query(simple_annotation_dict, task_query):
                    continue
            pixel_count = self.get_pixel_count(simple_annotation_dict)
            pixel_count_list.append(pixel_count)
        return pixel_count_list

class PixelCountCsvByAttribute:
    def __init__(self, selective_attribute_value_max_count: int = 20) -> None:
        self.selective_attribute_value_max_count = selective_attribute_value_max_count

    def _only_selective_attribute(self, columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
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
        self, pixel_count_list: Collection[AnnotationPixelCount], prior_attribute_columns: Optional[list[AttributeValueKey]]
    ) -> list[AttributeValueKey]:
        all_attr_key_set = {attr_key for c in pixel_count_list for attr_key in c.pixel_count_by_attribute}
        if prior_attribute_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_attribute_columns))
            remaining_columns_only_selective_attribute = self._only_selective_attribute(remaining_columns)
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
        value_columns = list(dict.fromkeys(value_columns).keys())
        return value_columns

    def get_columns(
        self,
        pixel_count_list: list[AnnotationPixelCount],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> list[AttributeValueKey]:
        basic_columns = [
            ("task_id", "", ""),
            ("task_status", "", ""),
            ("task_phase", "", ""),
            ("task_phase_stage", "", ""),
            ("input_data_id", "", ""),
            ("input_data_name", "", ""),
            ("pixel_count", "", ""),
        ]
        value_columns = self._value_columns(pixel_count_list, prior_attribute_columns)
        return basic_columns + value_columns

    def create_df(
        self,
        pixel_count_list: list[AnnotationPixelCount],
        prior_attribute_columns: Optional[list[AttributeValueKey]] = None,
    ) -> pandas.DataFrame:
        def to_cell(c: AnnotationPixelCount) -> dict[tuple[str, str, str], Any]:
            cell: dict[AttributeValueKey, Any] = {
                ("input_data_id", "", ""): c.input_data_id,
                ("input_data_name", "", ""): c.input_data_name,
                ("task_id", "", ""): c.task_id,
                ("task_status", "", ""): c.task_status.value,
                ("task_phase", "", ""): c.task_phase.value,
                ("task_phase_stage", "", ""): c.task_phase_stage,
                ("pixel_count", "", ""): c.pixel_count,
            }
            cell.update(c.pixel_count_by_attribute)
            return cell

        columns = self.get_columns(pixel_count_list, prior_attribute_columns)
        df = pandas.DataFrame([to_cell(e) for e in pixel_count_list], columns=pandas.MultiIndex.from_tuples(columns))
        value_columns = self._value_columns(pixel_count_list, prior_attribute_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df

class PixelCountCsvByLabel:
    def _value_columns(self, pixel_count_list: list[AnnotationPixelCount], prior_label_columns: Optional[list[str]]) -> list[str]:
        all_attr_key_set = {attr_key for elm in pixel_count_list for attr_key in elm.pixel_count_by_label.keys()}
        if prior_label_columns is not None:
            remaining_columns = sorted(all_attr_key_set - set(prior_label_columns))
            value_columns = prior_label_columns + remaining_columns
        else:
            remaining_columns = sorted(all_attr_key_set)
            value_columns = remaining_columns
        return value_columns

    def get_columns(
        self,
        pixel_count_list: list[AnnotationPixelCount],
        prior_label_columns: Optional[list[str]] = None,
    ) -> list[str]:
        basic_columns = [
            "task_id",
            "task_status",
            "task_phase",
            "task_phase_stage",
            "input_data_id",
            "input_data_name",
            "pixel_count",
        ]
        value_columns = self._value_columns(pixel_count_list, prior_label_columns)
        return basic_columns + value_columns

    def create_df(
        self,
        pixel_count_list: list[AnnotationPixelCount],
        prior_label_columns: Optional[list[str]] = None,
    ) -> pandas.DataFrame:
        def to_dict(c: AnnotationPixelCount) -> dict[str, Any]:
            d: dict[str, Any] = {
                "input_data_id": c.input_data_id,
                "input_data_name": c.input_data_name,
                "task_id": c.task_id,
                "task_status": c.task_status.value,
                "task_phase": c.task_phase.value,
                "task_phase_stage": c.task_phase_stage,
                "pixel_count": c.pixel_count,
            }
            d.update(c.pixel_count_by_label)
            return d

        columns = self.get_columns(pixel_count_list, prior_label_columns)
        df = pandas.DataFrame([to_dict(e) for e in pixel_count_list], columns=columns)
        value_columns = self._value_columns(pixel_count_list, prior_label_columns)
        df = df.fillna(dict.fromkeys(value_columns, 0))
        return df

class ListSegmentationPixelCountMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def print_pixel_count_csv(
        self, pixel_count_list: list[AnnotationPixelCount], csv_type: CsvType, output_file: Path, *, annotation_specs: Optional[AnnotationSpecs]
    ) -> None:
        if csv_type == CsvType.LABEL:
            label_columns: Optional[list[str]] = None
            if annotation_specs is not None:
                label_columns = annotation_specs.label_keys()
            df = PixelCountCsvByLabel().create_df(pixel_count_list, prior_label_columns=label_columns)
        elif csv_type == CsvType.ATTRIBUTE:
            attribute_columns: Optional[list[AttributeValueKey]] = None
            if annotation_specs is not None:
                attribute_columns = annotation_specs.selective_attribute_value_keys()
            df = PixelCountCsvByAttribute().create_df(pixel_count_list, prior_attribute_columns=attribute_columns)
        else:
            raise RuntimeError(f"{csv_type=}はサポートしていません。")
        print_csv(df, output_file)

    def print_pixel_count(
        self,
        annotation_path: Path,
        output_file: Path,
        arg_format: FormatArgument,
        *,
        project_id: Optional[str] = None,
        target_task_ids: Optional[Collection[str]] = None,
        task_query: Optional[TaskQuery] = None,
        csv_type: Optional[CsvType] = None,
    ) -> None:
        annotation_specs: Optional[AnnotationSpecs] = None
        non_selective_attribute_name_keys: Optional[list[AttributeNameKey]] = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id, annotation_type=DefaultAnnotationType.SEGMENTATION.value)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        pixel_count_list = ListSegmentationPixelCountByInputData(
            non_target_attribute_names=non_selective_attribute_name_keys
        ).get_pixel_count_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        logger.info(f"{len(pixel_count_list)} 件のタスクに含まれる塗りつぶしアノテーションのピクセル数情報を出力します。")

        if arg_format == FormatArgument.CSV:
            assert csv_type is not None
            self.print_pixel_count_csv(
                pixel_count_list, output_file=output_file, csv_type=csv_type, annotation_specs=annotation_specs
            )
        elif arg_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
            json_is_pretty = arg_format == FormatArgument.PRETTY_JSON
            print_json(
                [e.to_dict(encode_json=True) for e in pixel_count_list],
                is_pretty=json_is_pretty,
                output=output_file,
            )

class ListSegmentationPixelCount(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics list_segmentation_pixel_count: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(
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
            if project["input_data_type"] != InputDataType.IMAGE.value:
                logger.warning(
                    f"project_id='{project_id}'であるプロジェクトは、画像プロジェクトでないので、出力されるピクセル数はすべて0になります。"
                )

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        csv_type = CsvType(args.type)
        output_file: Path = args.output
        arg_format = FormatArgument(args.format)
        main_obj = ListSegmentationPixelCountMain(self.service)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_pixel_count(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Optional[Path]) -> None:
            if annotation_path is None:
                annotation_path = temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=is_latest,
                )
            main_obj.print_pixel_count(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_pixel_count(
                    project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path
                )
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_pixel_count(
                        project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path
                    )
        else:
            assert annotation_path is not None
            main_obj.print_pixel_count(
                project_id=project_id,
                csv_type=csv_type,
                arg_format=arg_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
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
        "``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やCSV列順が決まります。",
    )

    parser.add_argument(
        "--type",
        type=str,
        choices=[e.value for e in CsvType],
        default=CsvType.LABEL.value,
        help="出力するCSVの種類を指定してください。 ``--format csv`` を指定したときのみ有効なオプションです。\n"
        "\n"
        "* label: ラベルごとにピクセル数が記載されているCSV\n"
        "* attribute: 属性値ごとにピクセル数が記載されているCSV",
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
    ListSegmentationPixelCount(service, facade, args).main()

def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_segmentation_pixel_count"
    subcommand_help = "ラベルごとまたは属性値ごとに塗りつぶしアノテーションのピクセル数を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
