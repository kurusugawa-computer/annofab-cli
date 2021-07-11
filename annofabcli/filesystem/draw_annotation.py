import argparse
import json
import logging
import sys
from functools import partial
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy
import pandas
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface, ArgumentParser, get_list_from_args
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import TaskQuery, match_annotation_with_task_query
from annofabcli.common.image import IsParserFunc, write_annotation_images_from_path
from annofabcli.common.typing import InputDataSize
from annofabcli.common.utils import read_multiheader_csv

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
                return

        if args.metadata_key_of_image_size is not None:
            if args.input_data_json is None:
                print(
                    f"{self.COMMON_MESSAGE} argument --metadata_key_of_image_size: "
                    f"`--metadata_key_of_image_size`を指定した場合、`--input_data_json`は必須です。",
                    file=sys.stderr,
                )
                return

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
            metadata_key_of_image_width=args.metadata_key_of_image_size[0]
            if args.metadata_key_of_image_size is not None
            else None,
            metadata_key_of_image_height=args.metadata_key_of_image_size[1]
            if args.metadata_key_of_image_size is not None
            else None,
            output_image_extension=args.image_extension,
            background_color=args.background_color,
            label_name_list=label_name_list,
            is_target_parser_func=is_target_parser_func,
        )
        if not result:
            logger.error(f"'{annotation_path}' のアノテーション情報の画像化に失敗しました。")


from pathlib import Path
from typing import Iterator, Union

Color = Union[str, Tuple[int, int, int]]


from typing import Dict

import PIL


class DrawAnnotationForOneImage:
    def __init__(
        self,
        label_color_dict: Dict[str, Color],
        target_label_names: Optional[Iterator[str]] = None,
        polyline_labels: Optional[Iterator[str]] = None,
    ) -> None:
        self.label_color_dict = label_color_dict
        self.target_label_names = set(target_label_names)
        self.polyline_labels = set(polyline_labels)

    def _draw_annotations(
        self,
        draw: PIL.ImageDraw.Draw,
        parser: SimpleAnnotationParser,
    ) -> PIL.ImageDraw.Draw:
        """
        1個の入力データに属するアノテーションlistを描画する

        Args:
            draw: draw: (IN/OUT) PillowのDrawing Object. 変更される。
            parser: Simple Annotationのparser
            label_color_dict: label_nameとRGBを対応付けたdict
            label_name_list: 画像化対象のlabel_name. Noneの場合は、すべてのlabel_nameが画像化対象です。

        Returns:
            アノテーションを描画した状態のDrawing Object
        """

        def draw_segmentation(data_uri: str, color: Color):
            # 外部ファイルを描画する
            with parser.open_outer_file(data_uri) as f:
                with PIL.Image.open(f) as outer_image:
                    draw.bitmap([0, 0], outer_image, fill=color)

        def draw_bounding_box(data: Dict[str, Any], color: Color):
            xy = [
                (data["left_top"]["x"], data["left_top"]["y"]),
                (data["right_bottom"]["x"], data["right_bottom"]["y"]),
            ]
            draw.rectangle(xy, outline=color)

        def draw_single_point(data: Dict[str, Any], color: Color, diameter: int = 5):
            point_x = data["point"]["x"]
            point_y = data["point"]["y"]
            draw.ellipse(
                [(point_x - diameter, point_y - diameter), (point_x + diameter, point_y + diameter)], outline=color
            )

        def draw_polygon(data: Dict[str, Any], color: Color):
            xy = [(e["x"], e["y"]) for e in data["points"]]
            draw.polygon(xy, fill=color)

        def draw_polyline(data: Dict[str, Any], color: Color):
            xy = [(e["x"], e["y"]) for e in data["points"]]
            draw.line(xy, fill=color)

        simple_annotation = parser.load_json()

        # 下層レイヤにあるアノテーションから順に画像化する
        # reversed関数を使う理由：`simple_annotation.details`は上層レイヤのアノテーションから順に格納されているため
        if self.label_name_set is not None:
            annotation_list = [e for e in reversed(simple_annotation["details"]) if e.label in self.label_name]
        else:
            annotation_list = list(reversed(simple_annotation["details"]))

        for annotation in annotation_list:
            data = annotation["data"]
            if data is None:
                # 画像全体アノテーション
                return draw

            label_name: str = annotation["label"]
            color = label_color_dict.get(label_name)
            if color is None:
                logger.warning(f"label_name = {label_name} のcolorが指定されていません。")
                color = (255, 255, 255)

            data_type = data["_type"]
            if data_type in {"SegmentationV2", "Segmentation"}:
                draw_segmentation(data["data_uri"], color=color)

            elif data_type == "BoundingBox":
                draw_bounding_box(data, color=color)

            elif data_type == "SinglePoint":
                draw_single_point(data, color=color)
            elif data_type == "Points":
                if label_name in self.polyline_labels:
                    draw_polyline(data, color=color)
                else:
                    draw_polygon(data, color=color)

        return draw

    def main(
        parser: SimpleAnnotationParser,
        image_path: Path,
        output_file: Path,
    ):
        with PIL.Image.open(image_path) as image:
            image_size = image.size
            draw = PIL.ImageDraw.Draw(image)

        draw = PIL.ImageDraw.Draw(image)

        self._draw_annotations(draw, parser, label_color_dict, label_name_list=label_name_list)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_image_file)


def draw_annotation_all(
    iter_parser: Iterator[SimpleAnnotationParser],
    image_dir: Path,
    input_data_id_relation_dict: Dict[str, str],
    output_dir: Path,
):
    count = 0
    for parser in iter_parser:
        logger.debug(f"{parser.json_file_path} を読み込みます。")
        # if is_target_parser_func is not None and not is_target_parser_func(parser):
        #     logger.debug(f"{parser.json_file_path} の画像化をスキップします。")
        #     continue

        output_image_file = output_dir_path / f"{Path(parser.json_file_path).stem}.{output_image_extension}"
        tmp_image_size = _get_image_size(parser.input_data_id)
        if tmp_image_size is None:
            logger.warning(f"task_id={parser.task_id}, input_data_id={parser.input_data_id}: 画像サイズを取得できなかったので、スキップします。")
            continue

        write_annotation_image(
            parser,
            image_size=tmp_image_size,
            label_color_dict=label_color_dict,
            background_color=background_color,
            output_image_file=output_image_file,
            label_name_list=label_name_list,
        )
        logger.debug(f"画像ファイル '{str(output_image_file)}' を生成しました。")
        count_created_image += 1


class DrawAnnotation(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args

        annotation_path: Path = args.annotation
        # Simpleアノテーションの読み込み
        if annotation_path.is_file():
            iter_parser = lazy_parse_simple_annotation_zip(annotation_path)
        else:
            iter_parser = lazy_parse_simple_annotation_dir(annotation_path)

        csv_header: int = args.csv_header
        csv_path: Path = args.csv
        if csv_header == 1:
            original_df = pandas.read_csv(str(csv_path))
        else:
            original_df = read_multiheader_csv(str(csv_path), header_row_count=csv_header)

        df = create_masked_user_info_df(
            df=original_df,
            not_masked_biography_set=not_masked_biography_set,
            not_masked_user_id_set=not_masked_user_id_set,
        )
        self.print_csv(df)


def main(args):
    DrawAnnotation().main(args)


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation", type=Path, required=True, help="AnnoFabからダウンロードしたアノテーションzip、またはzipを展開したディレクトリを指定してください。"
    )

    parser.add_argument("--image_dir", type=Path, required=True, help="画像が存在するディレクトリを指定してください。")

    parser.add_argument(
        "--input_data_id_csv",
        type=Path,
        required=True,
        help="'input_data_id'と`--image_dir`配下の画像ファイルを紐付けたCSVを指定してください。"
        "CSVのフォーマットは、「1列目:input_data_id, 2列目:画像ファイルのパス」です。"
        "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/filesystem/draw_annotation.html を参照してください。",
    )

    parser.add_argument(
        "--label_color",
        type=str,
        required=True,
        help='label_nameとRGBの関係をJSON形式で指定します。ex) `{"dog":[255,128,64], "cat":[0,0,255]}`'
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument(
        "-o", "--output_dir", type=str, required=True, help="出力先ディレクトリのパスを指定してください。ディレクトリの構造はアノテーションzipと同じです。"
    )

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=False,
        help="描画対象のアノテーションのlabel_nameを指定します。指定しない場合は、すべてのlabel_nameが描画対象になります。"
        "`file://`を先頭に付けると、label_name の一覧が記載されたファイルを指定できます。",
    )

    argument_parser.add_task_id(
        required=False,
        help_message=(
            "描画対象であるタスクのtask_idを指定します。"
            "指定しない場合、すべてのタスクに含まれるアノテーションが描画されます。"
            "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="描画対象のタスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "draw_annotation"

    subcommand_help = "画像にアノテーションを描画します。"

    description = "画像にアノテーションを描画します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
