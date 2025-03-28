from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import numpy
import numpy as np
from annofabapi.segmentation import read_binary_image

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def remove_overlap_of_binary_image_array(
    binary_image_array_by_annotation: dict[str, np.ndarray], annotation_id_list: list[str]
) -> dict[str, np.ndarray]:
    """
    塗りつぶし画像の重なりを除去したbool配列をdictで返します。

    Args:
        binary_image_array_by_annotation: annotation_idをkeyとし、塗りつぶし画像のbool配列をvalueとするdict
        annotation_id_list: 塗りつぶし画像のannotation_idのlist。背面から前面の順に格納されている

    Returns:
        重なりを除去した塗りつぶし画像のbool配列が格納されているdict。keyはannotation_id

    """
    assert set(binary_image_array_by_annotation.keys()) == set(annotation_id_list)

    whole_2d_array = None  # 複数の塗りつぶしアノテーションを1枚に重ね合わせた状態。各要素はannotation_id

    # 背面から塗りつぶしアノテーションのbool配列を重ねていく
    for annotation_id in annotation_id_list:
        input_binary_image_array = binary_image_array_by_annotation[annotation_id]
        if whole_2d_array is None:
            whole_2d_array = numpy.full(input_binary_image_array.shape, "", dtype=str)

        whole_2d_array = np.where(input_binary_image_array, annotation_id, whole_2d_array)

    output_binary_image_array_by_annotation = {}
    for annotation_id in annotation_id_list:
        output_binary_image_array = whole_2d_array == annotation_id
        output_binary_image_array_by_annotation[annotation_id] = output_binary_image_array

    return output_binary_image_array_by_annotation


def foo(details: list[dict[str, Any]], output_dir: Path):
    original_2d_array = {}
    result_2d_array = None
    for detail in details:
        if detail["body"]["_type"] != "Outer":
            continue

        # download
        bool_2d_array = read_binary_image(fp)
        original_2d_array[detail["annotation_id"]] = bool_2d_array

        # 重なり
        if result_2d_array is not None:
            result_2d_array = numpy.full(bool_2d_array.shape, "", dtype=str)

        result_2d_array = np.where(bool_2d_array, detail["annotation_id"], result_2d_array)


class CopyAnnotation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation copy: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        # main_obj = CopyAnnotationMain(
        #     self.service,
        #     project_id=project_id,
        #     all_yes=self.all_yes,
        #     overwrite=args.overwrite,
        #     merge=args.merge,
        #     force=args.force,
        # )
        # main_obj.copy_annotations(copy_target_list, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    INPUT_HELP_MESSAGE = """
    アノテーションのコピー元とコピー先を':'で区切って指定します。

    タスク単位でコピーする場合の例： ``src_task_id:dest_task_id``
    入力データ単位でコピーする場合： ``src_task_id/src_input_data_id:dest_task_id/dest_input_data_id``
    ``file://`` を先頭に付けると、コピー元とコピー先が記載されているファイルを指定できます。
    """  # noqa: N806
    parser.add_argument("--input", type=str, nargs="+", required=True, help=INPUT_HELP_MESSAGE)

    overwrite_merge_group = parser.add_mutually_exclusive_group()
    overwrite_merge_group.add_argument(
        "--overwrite",
        action="store_true",
        help="コピー先にアノテーションが存在する場合、 ``--overwrite`` を指定していれば、すでに存在するアノテーションを削除してコピーします。"
        "指定しなければ、アノテーションのコピーをスキップします。",
    )
    overwrite_merge_group.add_argument(
        "--merge",
        action="store_true",
        help="コピー先にアノテーションが存在する場合、 ``--merge`` を指定していればアノテーションをannotation_id単位でマージしながらコピーします。"
        "annotation_idが一致すればアノテーションを上書き、一致しなければアノテーションを追加します。"
        "指定しなければ、アノテーションのコピーをスキップします。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="過去に割り当てられていて現在の担当者が自分自身でない場合、タスクの担当者を一時的に自分自身に変更してからアノテーションをコピーします。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="並列度。指定しない場合は、逐次的に処理します。指定した場合は、``--yes`` も指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "fix_segmentation_overlap"
    subcommand_help = "塗りつぶしアノテーションの重なりを除去します。"
    description = (
        "塗りつぶしアノテーションの重なりを除去します。インスタンスセグメンテーションは重ねることができてしまいます。この重なりを除去できます。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
