from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnnotationBoundingBoxInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    label: str
    annotation_id: str
    left_top: dict[str, int]
    right_bottom: dict[str, int]
    center: dict[str, float]
    """バウンディングボックスの中心座標"""
    width: int
    height: int
    area: int
    """バウンディングボックスの面積"""
    attributes: dict[str, str | int | bool]


def get_annotation_bounding_box_info_list(simple_annotation: dict[str, Any], *, target_label_names: Collection[str] | None = None) -> list[AnnotationBoundingBoxInfo]:
    result = []
    target_label_names_set = set(target_label_names) if target_label_names is not None else None
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] == "BoundingBox":
            label = detail["label"]
            # ラベル名によるフィルタリング
            if target_label_names_set is not None and label not in target_label_names_set:
                continue

            left_top = detail["data"]["left_top"]
            right_bottom = detail["data"]["right_bottom"]
            width = abs(right_bottom["x"] - left_top["x"])
            height = abs(right_bottom["y"] - left_top["y"])
            center_x = (left_top["x"] + right_bottom["x"]) / 2
            center_y = (left_top["y"] + right_bottom["y"]) / 2
            area = width * height

            result.append(
                AnnotationBoundingBoxInfo(
                    project_id=simple_annotation["project_id"],
                    task_id=simple_annotation["task_id"],
                    task_phase=simple_annotation["task_phase"],
                    task_phase_stage=simple_annotation["task_phase_stage"],
                    task_status=simple_annotation["task_status"],
                    input_data_id=simple_annotation["input_data_id"],
                    input_data_name=simple_annotation["input_data_name"],
                    label=label,
                    annotation_id=detail["annotation_id"],
                    left_top=left_top,
                    right_bottom=right_bottom,
                    center={"x": center_x, "y": center_y},
                    width=width,
                    height=height,
                    area=area,
                    updated_datetime=simple_annotation["updated_datetime"],
                    attributes=detail["attributes"],
                )
            )

    return result


def get_annotation_bounding_box_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> list[AnnotationBoundingBoxInfo]:
    annotation_bbox_list = []
    target_task_ids = set(target_task_ids) if target_task_ids is not None else None
    iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)
    logger.info(f"アノテーションZIPまたはディレクトリ'{annotation_path}'を読み込みます。")
    for index, parser in enumerate(iter_parser):
        if (index + 1) % 10000 == 0:
            logger.info(f"{index + 1}  件目のJSONを読み込み中")
        if target_task_ids is not None and parser.task_id not in target_task_ids:
            continue
        dict_simple_annotation = parser.load_json()
        if task_query is not None and not match_annotation_with_task_query(dict_simple_annotation, task_query):
            continue
        sub_annotation_bbox_list = get_annotation_bounding_box_info_list(dict_simple_annotation, target_label_names=target_label_names)
        annotation_bbox_list.extend(sub_annotation_bbox_list)
    return annotation_bbox_list


def create_df(
    annotation_bbox_list: list[AnnotationBoundingBoxInfo],
) -> pandas.DataFrame:
    base_columns = [
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
        "center.x",
        "center.y",
        "width",
        "height",
        "area",
    ]

    if not annotation_bbox_list:
        # 空のリストの場合は、base_columnsのみで空のDataFrameを返す
        return pandas.DataFrame(columns=base_columns)

    tmp_annotation_bbox_list = [e.to_dict(encode_json=True) for e in annotation_bbox_list]
    df = pandas.json_normalize(tmp_annotation_bbox_list)

    attribute_columns = sorted(col for col in df.columns if col.startswith("attributes."))
    columns = base_columns + attribute_columns

    return df[columns]


def print_annotation_bounding_box(
    annotation_path: Path,
    output_file: Path,
    output_format: FormatArgument,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> None:
    annotation_bbox_list = get_annotation_bounding_box_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
        target_label_names=target_label_names,
    )

    logger.info(f"{len(annotation_bbox_list)} 件のバウンディングボックスアノテーションの情報を出力します。 :: output='{output_file}'")

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
        raise ValueError(f"出力形式 '{output_format}' はサポートされていません。")


class ListAnnotationBoundingBox2d(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_bounding_box_annotation: error:"

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

        project_id: str | None = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.IMAGE.value:
                print(f"project_id='{project_id}'であるプロジェクトは画像プロジェクトでないので、終了します", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        label_name_list = get_list_from_args(args.label_name) if args.label_name is not None else None

        output_file: Path = args.output
        output_format = FormatArgument(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_bbox(project_id: str, temp_dir: Path, *, is_latest: bool) -> None:
            annotation_path = temp_dir / f"{project_id}__annotation.zip"
            downloading_obj.download_annotation_zip(
                project_id,
                dest_path=annotation_path,
                is_latest=is_latest,
            )
            print_annotation_bounding_box(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_bbox(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_bbox(
                        project_id=project_id,
                        temp_dir=Path(str_temp_dir),
                        is_latest=args.latest,
                    )
        else:
            assert annotation_path is not None
            print_annotation_bounding_box(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。",
    )

    group.add_argument("-p", "--project_id", type=str, help="project_id。アノテーションZIPをダウンロードします。")

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
        "--label_name",
        type=str,
        nargs="+",
        help="指定したラベル名のバウンディングボックスアノテーションのみを対象にします。複数指定できます。",
    )

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


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_bounding_box_annotation"
    subcommand_help = "アノテーションZIPからバウンディングボックス（矩形）アノテーションの座標情報を出力します。"
    epilog = "アノテーションZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
