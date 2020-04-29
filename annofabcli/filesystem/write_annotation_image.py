"""
Semantic Segmentation(Multi Class)用の画像を生成する。
"""

import argparse
import logging
import zipfile
from pathlib import Path
from typing import List, Optional

from annofabapi.models import TaskStatus
from annofabapi.parser import SimpleAnnotationParser

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser
from annofabcli.common.image import IsParserFunc, write_annotation_images_from_path

logger = logging.getLogger(__name__)

zipfile.is_zipfile("ab")


class WriteAnnotationImage:
    @staticmethod
    def create_is_target_parser_func(
        task_status_complete: bool = False, task_id_list: Optional[List[str]] = None
    ) -> IsParserFunc:
        def is_target_parser(parser: SimpleAnnotationParser) -> bool:
            simple_annotation = parser.parse()
            if task_status_complete:
                if simple_annotation.task_status != TaskStatus.COMPLETE:
                    logger.debug(
                        f"task_statusがcompleteでない( {simple_annotation.task_status.value})ため、"
                        f"{simple_annotation.task_id}, {simple_annotation.input_data_name} はスキップします。"
                    )
                    return False

            if task_id_list is not None and len(task_id_list) > 0:
                if simple_annotation.task_id not in task_id_list:
                    logger.debug(
                        f"画像化対象外のタスク {simple_annotation.task_id} であるため、 {simple_annotation.input_data_name} はスキップします。"
                    )
                    return False

            return True

        return is_target_parser

    def main(self, args):
        logger.info(f"args: {args}")

        image_size = annofabcli.common.cli.get_input_data_size(args.image_size)
        if image_size is None:
            logger.error("--image_size のフォーマットが不正です")
            return

        # label_color_dict を取得する
        label_color_dict = annofabcli.common.cli.get_json_from_args(args.label_color)
        label_color_dict = {k: tuple(v) for k, v in label_color_dict.items()}

        annotation_path = Path(args.annotation)
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        is_target_parser_func = self.create_is_target_parser_func(args.task_status_complete, task_id_list)

        # 画像生成
        result = write_annotation_images_from_path(
            annotation_path,
            image_size=image_size,
            label_color_dict=label_color_dict,
            output_dir_path=Path(args.output_dir),
            output_image_extension=args.image_extension,
            background_color=args.background_color,
            is_target_parser_func=is_target_parser_func,
        )
        if not result:
            logger.error(f"'{annotation_path}' のアノテーション情報の画像化に失敗しました。")


def main(args):
    WriteAnnotationImage().main(args)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument("--annotation", type=str, required=True, help="アノテーションzip、またはzipを展開したディレクトリ")

    parser.add_argument("--image_size", type=str, required=True, help="入力データ画像のサイズ。{width}x{height}。ex) 1280x720")

    parser.add_argument(
        "--label_color",
        type=str,
        required=True,
        help='label_nameとRGBの関係をJSON形式で指定します。ex) `{"dog":[255,128,64], "cat":[0,0,255]}`'
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.add_argument("--image_extension", type=str, default="png", help="出力画像の拡張子")

    parser.add_argument(
        "--background_color",
        type=str,
        help=(
            "アノテーションの画像の背景色を指定します。"
            'ex):  "rgb(173, 216, 230)", "lightgrey",  "#add8e6" '
            "[ImageColor Module](https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html) がサポートする文字列を利用できます。"  # noqa: E501
            "指定しない場合は、黒（rgb(0,0,0)）になります。"
        ),
    )

    parser.add_argument("--task_status_complete", action="store_true", help="taskのstatusがcompleteの場合のみ画像を生成します。")

    argument_parser.add_task_id(
        required=False,
        help_message=(
            "画像化するタスクのtask_idを指定します。" "指定しない場合、すべてのタスクが画像化されます。" "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_annotation_image"

    subcommand_help = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"

    description = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。" + "矩形、ポリゴン、塗りつぶし、塗りつぶしv2が対象。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
