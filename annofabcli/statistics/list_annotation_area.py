from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import zipfile
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy
import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
from annofabapi.segmentation import read_binary_image
from dataclasses_json import DataClassJsonMixin

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

logger = logging.getLogger(__name__)


def lazy_parse_simple_annotation_by_input_data(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
    if not annotation_path.exists():
        raise RuntimeError(f"'{annotation_path}' は存在しません。")

    if annotation_path.is_dir():
        return lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        return lazy_parse_simple_annotation_zip(annotation_path)
    else:
        raise RuntimeError(f"'{annotation_path}'は、zipファイルまたはディレクトリではありません。")


@dataclass(frozen=True)
class AnnotationAreaInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    label: str
    annotation_id: str
    annotation_area: int


def calculate_bounding_box_area(data: dict[str, Any]) -> int:
    width = abs(data["right_bottom"]["x"] - data["left_top"]["x"])
    height = abs(data["right_bottom"]["y"] - data["left_top"]["y"])
    return width * height


def calculate_segmentation_area(outer_file: Path) -> int:
    nd_array = read_binary_image(outer_file)
    return numpy.count_nonzero(nd_array)


def get_annotation_area_info_list(parser: SimpleAnnotationParser, simple_annotation: dict[str, Any]) -> list[AnnotationAreaInfo]:
    result = []
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] in {"Segmentation", "SegmentationV2"}:
            annotation_area = calculate_segmentation_area(parser.open_outer_file(detail["data"]["data_uri"]))
        elif detail["data"]["_type"] == "BoundingBox":
            annotation_area = calculate_bounding_box_area(detail["data"])

        else:
            continue

        result.append(
            AnnotationAreaInfo(
                project_id=simple_annotation["project_id"],
                task_id=simple_annotation["task_id"],
                task_phase=simple_annotation["task_phase"],
                task_phase_stage=simple_annotation["task_phase_stage"],
                task_status=simple_annotation["task_status"],
                input_data_id=simple_annotation["input_data_id"],
                input_data_name=simple_annotation["input_data_name"],
                label=detail["label"],
                annotation_id=detail["annotation_id"],
                annotation_area=annotation_area,
            )
        )

    return result


def get_annotation_area_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Optional[Collection[str]] = None,
    task_query: Optional[TaskQuery] = None,
) -> list[AnnotationAreaInfo]:
    annotation_area_list = []
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
        sub_annotation_area_list = get_annotation_area_info_list(parser, simple_annotation_dict)
        annotation_area_list.extend(sub_annotation_area_list)
    return annotation_area_list


def create_df(
    annotation_area_list: list[AnnotationAreaInfo],
) -> pandas.DataFrame:
    columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "label",
        "annotation_id",
        "annotation_area",
    ]
    df = pandas.DataFrame(e.to_dict() for e in annotation_area_list)
    if len(df) == 0:
        df = pandas.DataFrame(columns=columns)

    df = df.fillna({"annotation_area": 0})
    return df[columns]


def print_annotation_area(
    annotation_path: Path,
    output_file: Path,
    output_format: FormatArgument,
    *,
    target_task_ids: Optional[Collection[str]] = None,
    task_query: Optional[TaskQuery] = None,
) -> None:
    annotation_area_list = get_annotation_area_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
    )

    logger.info(f"{len(annotation_area_list)} 件のタスクに含まれる塗りつぶしアノテーションのピクセル数情報を出力します。")

    if output_format == FormatArgument.CSV:
        df = create_df(annotation_area_list)
        print_csv(df, output_file)

    elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
        json_is_pretty = output_format == FormatArgument.PRETTY_JSON
        print_json(
            [e.to_dict(encode_json=True) for e in annotation_area_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise RuntimeError(f"出力形式 '{output_format}' はサポートされていません。")


class ListAnnotationArea(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics list_annotation_area: error:"

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
            if project["input_data_type"] != InputDataType.IMAGE.value:
                logger.warning(f"project_id='{project_id}'であるプロジェクトは、画像プロジェクトでないので、出力されるデータは0件になります。")

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        output_file: Path = args.output
        output_format = FormatArgument(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_area(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Optional[Path]) -> None:
            if annotation_path is None:
                annotation_path = temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=is_latest,
                )
            print_annotation_area(
                output_format=output_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_area(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_area(project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            assert annotation_path is not None
            print_annotation_area(
                output_format=output_format,
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
    ListAnnotationArea(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_area"
    subcommand_help = "塗りつぶしアノテーションまたは矩形アノテーションの面積を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
