"""
Semantic Segmentation(Multi Class)用の画像を生成する。
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple  # pylint: disable=unused-import

from annofabapi.models import TaskStatus
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser
from annofabcli.common.image import write_annotation_image
from annofabcli.common.typing import RGB, InputDataSize

logger = logging.getLogger(__name__)


class WriteAnnotationImage:
    @staticmethod
    def write_annotation_images(iter_lazy_parser: Iterator[SimpleAnnotationParser],
                                default_input_data_size: InputDataSize, label_color_dict: Dict[str, RGB],
                                output_dir: Path, output_image_extension: str, task_status_complete: bool = False,
                                task_id_list: Optional[List[str]] = None, background_color: Optional[str] = None):

        for parser in iter_lazy_parser:
            logger.debug(f"{parser.json_file_path} を読み込みます。")
            simple_annotation = parser.parse()

            if task_status_complete:
                if simple_annotation.task_status != TaskStatus.COMPLETE:
                    logger.debug(f"task_statusがcompleteでない( {simple_annotation.task_status.value})ため、"
                                 f"{simple_annotation.task_id, simple_annotation.input_data_name} はスキップする。")
                    continue

            if task_id_list is not None and len(task_id_list) > 0:
                if simple_annotation.task_id not in task_id_list:
                    logger.debug(f"タスク {simple_annotation.task_id} はスキップする")
                    continue

            output_image_file = output_dir / f"{parser.json_file_path}.{output_image_extension}"
            write_annotation_image(parser, image_size=default_input_data_size, label_color_dict=label_color_dict,
                                   background_color=background_color, output_image_file=output_image_file)

            logger.debug(f"{str(output_image_file)} の生成完了.")

    def main(self, args):
        annofabcli.common.cli.load_logging_config_from_args(args)
        logger.info(f"args: {args}")

        default_input_data_size = annofabcli.common.cli.get_input_data_size(args.input_data_size)
        if default_input_data_size is None:
            logger.error("--default_input_data_size のフォーマットが不正です")
            return

        try:
            with open(args.label_color_file) as f:
                label_color_dict = json.load(f)
                label_color_dict = {k: tuple(v) for k, v in label_color_dict.items()}

        except Exception as e:
            logger.error("--label_color_json_file のJSON Parseに失敗しました。")
            raise e

        annotation_path = Path(args.annotation)
        if annotation_path.is_dir():
            iter_lazy_parser = lazy_parse_simple_annotation_dir(annotation_path)
        elif annotation_path.suffix.lower() == ".zip":
            iter_lazy_parser = lazy_parse_simple_annotation_zip(annotation_path)
        else:
            logger.error("--annotation には、アノテーションzip、またはzipを展開したディレクトリのパスを渡してください。")
            return

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

        self.write_annotation_images(iter_lazy_parser=iter_lazy_parser, default_input_data_size=default_input_data_size,
                                     label_color_dict=label_color_dict, output_dir=Path(args.output_dir),
                                     output_image_extension=args.image_extension,
                                     task_status_complete=args.task_status_complete, task_id_list=task_id_list,
                                     background_color=args.background_color)


def main(args):
    WriteAnnotationImage().main(args)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument('--annotation', type=str, required=True, help='アノテーションzip、またはzipを展開したディレクトリ')

    parser.add_argument('--input_data_size', type=str, required=True, help='入力データ画像のサイズ。{width}x{height}。ex. 1280x720')

    parser.add_argument('--label_color_file', type=str, required=True,
                        help='label_nameとRGBを対応付けたJSONファイルのパス. key: label_name, value:[R,G,B]')

    parser.add_argument('--output_dir', type=str, required=True, help='出力ディレクトリのパス')

    parser.add_argument('--image_extension', type=str, default="png", help='出力画像の拡張子')

    parser.add_argument(
        '--background_color',
        type=str,
        help=(
            'アノテーションの画像の背景色を指定します。'
            'ex):  "rgb(173, 216, 230)", "lightgrey",  "#add8e6" '
            '[ImageColor Module](https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html) がサポートする文字列を利用できます。'  # noqa: E501
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))

    parser.add_argument('--task_status_complete', action="store_true", help='taskのstatusがcompleteの場合のみ画像を生成します。')

    argument_parser.add_task_id(
        required=False, help_message=('画像化するタスクのtask_idを指定します。'
                                      '指定しない場合、すべてのタスクが画像化されます。'
                                      '`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。'))

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_annotation_image"

    subcommand_help = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"

    description = ("アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"
                   "矩形、ポリゴン、塗りつぶし、塗りつぶしv2が対象。"
                   "複数のアノテーションディレクトリを指定して、画像をマージすることもできる。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
