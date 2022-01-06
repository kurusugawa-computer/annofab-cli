import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from annofabapi.models import InputData, TaskStatus
from annofabapi.parser import SimpleAnnotationParser

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser
from annofabcli.common.facade import TaskQuery, match_annotation_with_task_query
from annofabcli.common.image import IsParserFunc, write_annotation_images_from_path
from annofabcli.common.typing import InputDataSize

logger = logging.getLogger(__name__)


class WriteAnnotationImage:
    @staticmethod
    def create_is_target_parser_func(
        task_status_complete: bool = False,
        task_id_list: Optional[List[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> IsParserFunc:
        task_id_set = set(task_id_list) if task_id_list is not None else None

        def is_target_parser(parser: SimpleAnnotationParser) -> bool:
            dict_simple_annotation = parser.load_json()
            if task_status_complete:
                if dict_simple_annotation["task_status"] != TaskStatus.COMPLETE.value:
                    logger.debug(
                        f"task_statusがcompleteでない( {dict_simple_annotation['task_status']})ため、"
                        f"{parser.json_file_path} をスキップします。"
                    )
                    return False

            if task_id_set is not None and len(task_id_set) > 0:
                if dict_simple_annotation["task_id"] not in task_id_set:
                    logger.debug(f"画像化対象外のタスクであるため、 {parser.json_file_path} をスキップします。")
                    return False

            if task_query is not None and not match_annotation_with_task_query(dict_simple_annotation, task_query):
                return False

            return True

        return is_target_parser

    COMMON_MESSAGE = "annofabcli filesystem write_annotation_image: error:"

    @staticmethod
    def get_input_data_dict(input_data_json: Path) -> Dict[str, InputData]:
        with input_data_json.open() as f:
            logger.debug(f"{input_data_json} を読み込み中")
            input_data_list = json.load(f)
            logger.debug(f"{len(input_data_list)} 件をDictに変換中")
            return {e["input_data_id"]: e for e in input_data_list}

    def main(self, args):
        logger.info(f"args: {args}")

        image_size: Optional[InputDataSize] = None
        if args.image_size is not None:
            image_size = annofabcli.common.cli.get_input_data_size(args.image_size)
            if image_size is None:
                logger.error("--image_size のフォーマットが不正です")
                print(
                    f"{self.COMMON_MESSAGE} argument --image_size: フォーマットが不正です。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        # label_color_dict を取得する
        label_color_dict = annofabcli.common.cli.get_json_from_args(args.label_color)
        label_color_dict = {k: tuple(v) for k, v in label_color_dict.items()}
        label_name_list = (
            annofabcli.common.cli.get_list_from_args(args.label_name) if args.label_name is not None else None
        )
        annotation_path: Path = args.annotation
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        if args.task_status_complete:
            logger.warning(f"'--task_status_complete' は非推奨です。わりに'--task_query` を使ってください。")

        is_target_parser_func = self.create_is_target_parser_func(
            args.task_status_complete, task_id_list=task_id_list, task_query=task_query
        )

        input_data_dict = self.get_input_data_dict(args.input_data_json) if args.input_data_json is not None else None

        # 画像生成
        result = write_annotation_images_from_path(
            annotation_path,
            label_color_dict=label_color_dict,
            output_dir_path=Path(args.output_dir),
            image_size=image_size,
            input_data_dict=input_data_dict,
            output_image_extension=args.image_extension,
            background_color=args.background_color,
            label_name_list=label_name_list,
            is_target_parser_func=is_target_parser_func,
        )
        if not result:
            logger.error(f"'{annotation_path}' のアノテーション情報の画像化に失敗しました。")


def main(args):
    WriteAnnotationImage().main(args)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument("--annotation", type=Path, required=True, help="アノテーションzip、またはzipを展開したディレクトリ")

    image_size_group = parser.add_mutually_exclusive_group(required=True)

    image_size_group.add_argument("--image_size", type=str, help="画像サイズ。{width}x{height}。ex) 1280x720")

    image_size_group.add_argument(
        "--input_data_json",
        type=Path,
        help="入力データ情報が記載されたJSONファイルのパスを指定してください。"
        "入力データのプロパティ ``system_metadata.original_resolution`` を参照して画像サイズを決めます。"
        "JSONファイルは ``$ annofabcli project download input_data`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=False,
        help="画像化対象のlabel_nameを指定します。指定しない場合は、すべてのlabel_nameが画像化対象になります。"
        " ``file://`` を先頭に付けると、label_name の一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--label_color",
        type=str,
        required=True,
        help='label_nameとRGBの関係をJSON形式で指定します。ex) ``{"dog":[255,128,64], "cat":[0,0,255]}``\n'
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "--image_extension",
        type=str,
        default="png",
        choices=["png", "bmp", "jpeg", "jpg", "gif", "tif", "tiff"],
        help="出力画像の拡張子を指定してください。",
    )

    parser.add_argument(
        "--background_color",
        type=str,
        help=(
            "アノテーションの画像の背景色を指定します。"
            'ex):  "rgb(173, 216, 230)", "lightgrey",  "#add8e6" '
            "[ImageColor Module](https://pillow.readthedocs.io/en/stable/reference/ImageColor.html) がサポートする文字列を利用できます。"  # noqa: E501
            "指定しない場合は、黒（rgb(0,0,0)）になります。"
        ),
    )

    parser.add_argument(
        "--task_status_complete",
        action="store_true",
        help="taskのstatusがcompleteの場合のみ画像を生成します。ただし非推奨です。替わりに ``--task_query`` を使ってください。",
    )

    argument_parser.add_task_id(
        required=False,
        help_message=(
            "画像化するタスクのtask_idを指定します。" "指定しない場合、すべてのタスクが画像化されます。" " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_annotation_image"

    subcommand_help = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"

    description = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。" + "矩形、ポリゴン、塗りつぶし、塗りつぶしv2が対象。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
