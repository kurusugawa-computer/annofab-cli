import argparse
import logging
import sys
import tempfile
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy
import pandas
from annofabapi.exceptions import AnnotationOuterFileNotFoundError
from annofabapi.models import InputDataType, ProjectMemberRole
from annofabapi.segmentation import read_binary_image
from annofabapi.util.page import create_image_editor_url
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)

SEGMENTATION_DATA_TYPES = {"Segmentation", "SegmentationV2"}
"""塗りつぶしアノテーションのdata._typeの集合。"""


@dataclass(frozen=True)
class AnnotationSegmentationInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_phase: str
    task_phase_stage: int
    task_status: str

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時。"""

    label: str
    annotation_id: str
    annotation_editor_url: str
    annotation_type: str
    """アノテーションの種類。Segmentation または SegmentationV2。"""

    data_uri: str
    """塗りつぶし画像の外部ファイルを参照するURI。"""

    area: int | None
    """塗りつぶし領域の面積。外部ファイルを読み込めない場合はNone。"""

    bounding_box: dict[str, dict[str, int]] | None
    """塗りつぶし領域の外接矩形。外部ファイルを読み込めない場合や面積が0の場合はNone。"""

    bounding_box_width: int | None
    """外接矩形の幅。外部ファイルを読み込めない場合や面積が0の場合はNone。"""

    bounding_box_height: int | None
    """外接矩形の高さ。外部ファイルを読み込めない場合や面積が0の場合はNone。"""

    attributes: dict[str, Any]


def calculate_segmentation_properties(outer_file: Path | BinaryIO) -> tuple[int, dict[str, dict[str, int]] | None, int | None, int | None]:
    binary_image_array = read_binary_image(outer_file)
    area = int(numpy.count_nonzero(binary_image_array))
    if area == 0:
        return area, None, None, None

    yx_array = numpy.argwhere(binary_image_array)
    min_y, min_x = yx_array.min(axis=0)
    max_y, max_x = yx_array.max(axis=0)
    bounding_box = {
        "left_top": {"x": int(min_x), "y": int(min_y)},
        "right_bottom": {"x": int(max_x), "y": int(max_y)},
    }
    return area, bounding_box, int(max_x - min_x + 1), int(max_y - min_y + 1)


def get_segmentation_properties(
    data_uri: str,
    *,
    open_outer_file: Callable[[str], Path | BinaryIO] | None = None,
    annotation_id: str | None = None,
) -> tuple[int | None, dict[str, dict[str, int]] | None, int | None, int | None]:
    if open_outer_file is None:
        return None, None, None, None

    try:
        outer_file = open_outer_file(data_uri)
        return calculate_segmentation_properties(outer_file)
    except (AnnotationOuterFileNotFoundError, OSError, ValueError) as e:
        logger.warning(
            f"塗りつぶし画像を読み込めないため、面積と外接矩形をNoneにします。 annotation_id='{annotation_id}', data_uri='{data_uri}' :: {e}"
        )
        return None, None, None, None


def get_annotation_segmentation_info_list(
    simple_annotation: dict[str, Any],
    *,
    target_label_names: Collection[str] | None = None,
    open_outer_file: Callable[[str], Path | BinaryIO] | None = None,
) -> list[AnnotationSegmentationInfo]:
    result = []
    target_label_names_set = set(target_label_names) if target_label_names is not None else None
    for detail in simple_annotation["details"]:
        data = detail["data"]
        if data["_type"] not in SEGMENTATION_DATA_TYPES:
            continue

        label = detail["label"]
        # ラベル名によるフィルタリング
        if target_label_names_set is not None and label not in target_label_names_set:
            continue

        data_uri = data["data_uri"]
        area, bounding_box, bounding_box_width, bounding_box_height = get_segmentation_properties(
            data_uri,
            open_outer_file=open_outer_file,
            annotation_id=detail["annotation_id"],
        )
        result.append(
            AnnotationSegmentationInfo(
                project_id=simple_annotation["project_id"],
                task_id=simple_annotation["task_id"],
                task_phase=simple_annotation["task_phase"],
                task_phase_stage=simple_annotation["task_phase_stage"],
                task_status=simple_annotation["task_status"],
                input_data_id=simple_annotation["input_data_id"],
                input_data_name=simple_annotation["input_data_name"],
                label=label,
                annotation_id=detail["annotation_id"],
                annotation_editor_url=create_image_editor_url(
                    simple_annotation["project_id"],
                    simple_annotation["task_id"],
                    input_data_id=simple_annotation["input_data_id"],
                    annotation_id=detail["annotation_id"],
                ),
                annotation_type=data["_type"],
                data_uri=data_uri,
                area=area,
                bounding_box=bounding_box,
                bounding_box_width=bounding_box_width,
                bounding_box_height=bounding_box_height,
                updated_datetime=simple_annotation["updated_datetime"],
                attributes=detail["attributes"],
            )
        )

    return result


def get_annotation_segmentation_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> list[AnnotationSegmentationInfo]:
    annotation_segmentation_list = []
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
        sub_annotation_segmentation_list = get_annotation_segmentation_info_list(
            dict_simple_annotation,
            target_label_names=target_label_names,
            open_outer_file=parser.open_outer_file,
        )
        annotation_segmentation_list.extend(sub_annotation_segmentation_list)
    return annotation_segmentation_list


def create_df(
    annotation_segmentation_list: list[AnnotationSegmentationInfo],
) -> pandas.DataFrame:
    base_columns = [
        "project_id",
        "task_id",
        "task_phase",
        "task_phase_stage",
        "task_status",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "label",
        "annotation_id",
        "annotation_editor_url",
        "annotation_type",
        "data_uri",
        "area",
        "bounding_box.left_top.x",
        "bounding_box.left_top.y",
        "bounding_box.right_bottom.x",
        "bounding_box.right_bottom.y",
        "bounding_box_width",
        "bounding_box_height",
    ]

    if not annotation_segmentation_list:
        # 件数が0件のときも列ヘッダを出力する
        return pandas.DataFrame(columns=base_columns)

    tmp_annotation_segmentation_list = [e.to_dict(encode_json=True) for e in annotation_segmentation_list]
    df = pandas.json_normalize(tmp_annotation_segmentation_list)

    attribute_columns = sorted(col for col in df.columns if col.startswith("attributes."))
    columns = base_columns + attribute_columns

    for column in columns:
        if column not in df.columns:
            df[column] = pandas.NA

    return df[columns]


def print_annotation_segmentation(
    annotation_path: Path,
    output_file: Path,
    output_format: OutputFormat,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> None:
    annotation_segmentation_list = get_annotation_segmentation_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
        target_label_names=target_label_names,
    )

    logger.info(f"{len(annotation_segmentation_list)} 件の塗りつぶしアノテーションの情報を出力します。 :: output='{output_file}'")

    if output_format == OutputFormat.CSV:
        df = create_df(annotation_segmentation_list)
        print_csv(df, output_file)

    elif output_format in [OutputFormat.PRETTY_JSON, OutputFormat.JSON]:
        json_is_pretty = output_format == OutputFormat.PRETTY_JSON
        print_json(
            [e.to_dict(encode_json=True) for e in annotation_segmentation_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise ValueError(f"出力形式 '{output_format}' はサポートされていません。")


class ListAnnotationSegmentation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_segmentation_annotation: error:"

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

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        label_name_list = get_list_from_args(args.label_name) if args.label_name is not None else None

        output_file: Path = args.output
        output_format = OutputFormat(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_segmentation(project_id: str, temp_dir: Path, *, is_latest: bool) -> None:
            local_annotation_path = downloading_obj.download_annotation_zip_to_dir(
                project_id,
                temp_dir,
                is_latest=is_latest,
            )
            print_annotation_segmentation(
                local_annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_segmentation(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_segmentation(
                        project_id=project_id,
                        temp_dir=Path(str_temp_dir),
                        is_latest=args.latest,
                    )
        else:
            assert annotation_path is not None
            print_annotation_segmentation(
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
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
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
        help="指定したラベル名の塗りつぶしアノテーションのみを対象にします。複数指定できます。",
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
    ListAnnotationSegmentation(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_segmentation_annotation"
    subcommand_help = "アノテーションZIPから塗りつぶしアノテーションの情報を出力します。"
    epilog = "アノテーションZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
