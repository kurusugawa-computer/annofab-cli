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

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from annofabapi.parser import (
    SimpleAnnotationParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)
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
class AnnotationBoundingBoxInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    updated_datetime: Optional[str]
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    label: str
    annotation_id: str
    left_top: dict[str, float]
    right_bottom: dict[str, float]
    width: float
    height: float


def get_annotation_bounding_box_info_list(parser: SimpleAnnotationParser, simple_annotation: dict[str, Any]) -> list[AnnotationBoundingBoxInfo]:
    result = []
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] == "BoundingBox":
            left_top = detail["data"]["left_top"]
            right_bottom = detail["data"]["right_bottom"]
            width = abs(right_bottom["x"] - left_top["x"])
            height = abs(right_bottom["y"] - left_top["y"])

            result.append(
                AnnotationBoundingBoxInfo(
                    project_id=simple_annotation["project_id"],
                    task_id=simple_annotation["task_id"],
                    task_phase=simple_annotation["task_phase"],
                    task_phase_stage=simple_annotation["task_phase_stage"],
                    task_status=simple_annotation["task_status"],
                    input_data_id=simple_annotation["input_data_id"],
                    input_data_name=simple_annotation["input_data_name"],
                    label=detail["label"],
                    annotation_id=detail["annotation_id"],
                    left_top=left_top,
                    right_bottom=right_bottom,
                    width=width,
                    height=height,
                    updated_datetime=simple_annotation["updated_datetime"],
                )
            )

    return result


def get_annotation_bounding_box_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Optional[Collection[str]] = None,
    task_query: Optional[TaskQuery] = None,
) -> list[AnnotationBoundingBoxInfo]:
    annotation_bbox_list = []
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
        sub_annotation_bbox_list = get_annotation_bounding_box_info_list(parser, simple_annotation_dict)
        annotation_bbox_list.extend(sub_annotation_bbox_list)
    return annotation_bbox_list


def create_df(
    annotation_bbox_list: list[AnnotationBoundingBoxInfo],
) -> pandas.DataFrame:
    columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "label",
        "annotation_id",
        "left_top.x",
        "left_top.y",
        "right_bottom.x",
        "right_bottom.y",
        "width",
        "height",
    ]
    df = pandas.DataFrame()
    if len(annotation_bbox_list) > 0:
        df = pandas.DataFrame([{
            "project_id": e.project_id,
            "task_id": e.task_id,
            "task_status": e.task_status,
            "task_phase": e.task_phase,
            "task_phase_stage": e.task_phase_stage,
            "input_data_id": e.input_data_id,
            "input_data_name": e.input_data_name,
            "updated_datetime": e.updated_datetime,
            "label": e.label,
            "annotation_id": e.annotation_id,
            "left_top.x": e.left_top["x"],
            "left_top.y": e.left_top["y"],
            "right_bottom.x": e.right_bottom["x"],
            "right_bottom.y": e.right_bottom["y"],
            "width": e.width,
            "height": e.height,
        } for e in annotation_bbox_list])
    else:
        df = pandas.DataFrame(columns=columns)

    return df[columns]


def print_annotation_bounding_box(
    annotation_path: Path,
    output_file: Path,
    output_format: FormatArgument,
    *,
    target_task_ids: Optional[Collection[str]] = None,
    task_query: Optional[TaskQuery] = None,
) -> None:
    annotation_bbox_list = get_annotation_bounding_box_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
    )

    logger.info(f"{len(annotation_bbox_list)} 件のタスクに含まれるバウンディングボックスの情報を出力します。")

    if output_format == FormatArgument.CSV:
        df = create_df(annotation_bbox_list)
        print_csv(df, output_file)

    elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
        json_is_pretty = output_format == FormatArgument.PRETTY_JSON
        # DataClassJsonMixinを使用したtoJSON処理
        print_json(
            [e.to_dict(encode_json=True) for e in annotation_bbox_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise RuntimeError(f"出力形式 '{output_format}' はサポートされていません。")


class ListAnnotationBoundingBox2d(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_annotation_bounding_box_2d: error:"

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

        def download_and_print_annotation_bbox(project_id: str, temp_dir: Path, *, is_latest: bool, annotation_path: Optional[Path]) -> None:
            if annotation_path is None:
                annotation_path = temp_dir / f"{project_id}__annotation.zip"
                downloading_obj.download_annotation_zip(
                    project_id,
                    dest_path=annotation_path,
                    is_latest=is_latest,
                )
            print_annotation_bounding_box(
                output_format=output_format,
                output_file=output_file,
                target_task_ids=task_id_list,
                task_query=task_query,
                annotation_path=annotation_path,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_bbox(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_bbox(project_id=project_id, temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)
        else:
            assert annotation_path is not None
            print_annotation_bounding_box(
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
    ListAnnotationBoundingBox2d(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_bounding_box_2d"
    subcommand_help = "バウンディングボックス（矩形）アノテーションの座標情報を出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
