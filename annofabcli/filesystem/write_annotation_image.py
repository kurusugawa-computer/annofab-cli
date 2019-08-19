"""
Semantic Segmentation(Multi Class)用の画像を生成する。
"""

import argparse
import json
import logging
import os
import os.path
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Iterator  # pylint: disable=unused-import

import PIL
import PIL.Image
import PIL.ImageDraw
from annofabapi.models import Annotation

import annofabcli
import annofabcli.common.cli
from annofabcli.common.typing import RGB, InputDataSize, SubInputDataList
from annofabapi.parser import parse_simple_annotation_zip, LazySimpleAnnotationParser
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
logger = logging.getLogger(__name__)

# 型タイプ
AnnotationSortKeyFunc = Callable[[Annotation], Any]
"""アノテーションをsortするときのkey関数のType"""

def get_data_uri_of_outer_file(annotation: SimpleAnnotationDetail) -> Optional[str]:
    """
    外部ファイルの data_uri を取得する
    Args:
        annotation: アノテーション

    Returns:
        外部ファイルの data_uri

    """
    data = annotation.data
    if data is None:
        return None

    return data.get("data_uri")


def fill_annotation(draw: PIL.ImageDraw.Draw, annotation: SimpleAnnotationDetail, label_color_dict: Dict[str, RGB], outer_image: Optional[PIL.Image] = None) -> PIL.ImageDraw.Draw:
    """
    1個のアノテーションを、塗りつぶしで描画する。（矩形、ポリゴン、塗りつぶし、塗りつぶしv2）

    Args:
        draw: draw: (IN/OUT) PillowのDrawing Object. 変更される。
        annotation: 描画対象のアノテーション
        label_color_dict: label_nameとRGBを対応付けたdict
        outer_image: 外部ファイル（塗りつぶし）の画像オブジェクト

    Returns:
        アノテーションを描画した状態のDrawing Object
    """

    data = annotation.data
    if data is None:
        # 画像全体アノテーション
        return draw

    color = label_color_dict.get(annotation.label)
    if color is None:
        logger.warning(f"label_name = {annotation['label']} のcolorが指定されていません")
        color = (255, 255, 255)

    data_type = data["_type"]
    if data_type == "BoundingBox":
        xy = [(data["left_top"]["x"], data["left_top"]["y"]),
              (data["right_bottom"]["x"], data["right_bottom"]["y"])]
        draw.rectangle(xy, fill=color)

    elif data_type == "Points":
        # Polygon
        xy = [(e["x"], e["y"]) for e in data["points"]]
        draw.polygon(xy, fill=color)

    elif data_type in ["SegmentationV2", "Segmentation"]:
        # 塗りつぶしv2 or 塗りつぶし
        if outer_image is not None:
            draw.bitmap([0, 0], outer_image, fill=color)
        else:
            logger.warning(f"アノテーション種類が塗りつぶし or 塗りつぶしv2ですが、`outer_image`がNoneです。")

    return draw


def fill_annotation_list(draw: PIL.ImageDraw.Draw, parser: LazySimpleAnnotationParser, label_color_dict: Dict[str, RGB],
                         annotation_sort_key_func: Callable[[SimpleAnnotationDetail],int], exclude_annotion_func) -> PIL.ImageDraw.Draw:
    """
    1個の入力データに属するアノテーションlistを描画する

    Args:
        draw: draw: (IN/OUT) PillowのDrawing Object. 変更される。
        parser: annotationの遅延Parser
        label_color_dict: label_nameとRGBを対応付けたdict

    Returns:
        アノテーションを描画した状態のDrawing Object
    """
    simple_annotation = parser.parse()

    for annotation in reversed(simple_annotation.details):
        # 外部ファイルのImage情報を取得する
        data_uri_outer_image = get_data_uri_of_outer_file(annotation)
        if data_uri_outer_image is not None:
            with parser.open_outer_file(data_uri_outer_image) as f:
                outer_image = PIL.Image.open(f)

        # アノテーション情報を描画する
        fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=outer_image)

    return draw



def write_annotation_image(output_image_file: Path, parser: LazySimpleAnnotationParser,
                                          image_size: InputDataSize, label_color_dict: Dict[str, RGB],
                                            background_color: Optional[Any] = None):
    """
    アノテーション情報が記載されたJSONファイルから、Semantic Segmentation用の画像を生成する。
    Semantic Segmentation用のアノテーションがなくても、画像は生成する。
    """

    image = PIL.Image.new(mode="RGB", size=image_size, color=background_color)
    draw = PIL.ImageDraw.Draw(image)

    fill_annotation_list(draw, parser, label_color_dict)

    output_image_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_image_file)

    logger.info(f"{str(output_image_file)} の生成完了")



class WriteAnnotationImage:
    @staticmethod
    def _create_sub_input_data_list(sub_annotation_dir_list: List[str], input_data_json: Path) -> SubInputDataList:
        """
        マージ対象の sub_input_data_listを生成する
        """
        sub_input_data_list: SubInputDataList = []

        for sub_annotation_dir in sub_annotation_dir_list:
            sub_annotation_dir_path = Path(sub_annotation_dir)
            sub_input_data_json = sub_annotation_dir_path / str(
                input_data_json.relative_to(input_data_json.parent.parent))
            sub_input_data_dir = sub_input_data_json.parent / sub_input_data_json.stem

            elm = (str(sub_input_data_json), str(sub_input_data_dir))
            sub_input_data_list.append(elm)

        return sub_input_data_list



    def draw_sub_input_data(self, sub_input_data_list: SubInputDataList, label_color_dict: Dict[str, RGB],
                            draw: PIL.ImageDraw.Draw, task_status_complete: bool = False,
                            annotation_sort_key_func: Optional[AnnotationSortKeyFunc] = None) -> PIL.ImageDraw.Draw:
        """
        他のプロジェクトのアノテーション情報を描画する。
        Args:
            sub_input_data_list:
            label_color_dict:
            draw:
            task_status_complete:
            annotation_sort_key_func:

        Returns:

        """

        for sub_input_data_json_file, sub_input_data_dir in sub_input_data_list:
            if not os.path.exists(sub_input_data_json_file):
                logger.warning(f"{sub_input_data_json_file} は存在しません.")
                continue

            with open(sub_input_data_json_file) as f:
                sub_input_data_json = json.load(f)

            task_status = sub_input_data_json["task_status"]
            if task_status_complete and task_status != "complete":
                logger.warning(f"task_statusがcompleteでない( {task_status})ため、{sub_input_data_json_file} のアノテーションは描画しない")
                continue

            if annotation_sort_key_func is None:
                sub_annotation_list = list(reversed(sub_input_data_json["details"]))
            else:
                sub_annotation_list = sorted(sub_input_data_json["details"], key=annotation_sort_key_func)

            self.draw_annotation_list(sub_annotation_list, sub_input_data_dir, label_color_dict, draw)

        return draw

    def write_one_semantic_segmentation_image(self, input_data_json_file: str, input_data_dir: str,
                                              input_dat_size: InputDataSize, label_color_dict: Dict[str, RGB],
                                              output_image_file: str, task_status_complete: bool = False,
                                              annotation_sort_key_func: Optional[AnnotationSortKeyFunc] = None,
                                              sub_input_data_list: Optional[SubInputDataList] = None,
                                              str_background_color: Optional[str] = None):
        """
        アノテーション情報が記載されたJSONファイルから、Semantic Segmentation用の画像を生成する。
        Semantic Segmentation用のアノテーションがなくても、画像は生成する。

        Args:
            input_data_json_file: JSONファイルのパス
            input_data_dir: 塗りつぶしアノテーションが格納されたディレクトリのパス
            input_dat_size: 画像データのサイズ Tupple[width, height]
            label_color_dict: label_nameとRGBを対応付けたdict
            output_image_file: 出力する画像ファイル
            task_status_complete: Trueならばtask_statusがcompleteのときのみ画像を生成する。
            annotation_sort_key_func: アノテーションをsortするときのkey関数. Noneならばsortしない
            sub_input_data_list: マージ対象の入力データ情報

        """
        logger.debug(f"args: {input_data_json_file}, {input_data_dir}, {input_dat_size}, {output_image_file}")
        with open(input_data_json_file) as f:
            input_data_json = json.load(f)

        image = PIL.Image.new(mode="RGB", size=input_dat_size, color=str_background_color)
        draw = PIL.ImageDraw.Draw(image)

        # アノテーションを描画する
        if annotation_sort_key_func is None:
            annotation_list = list(reversed(input_data_json["details"]))
        else:
            annotation_list = sorted(input_data_json["details"], key=annotation_sort_key_func)

        self.draw_annotation_list(annotation_list, input_data_dir, label_color_dict, draw)

        if sub_input_data_list is not None:
            self.draw_sub_input_data(sub_input_data_list=sub_input_data_list, label_color_dict=label_color_dict,
                                     draw=draw, task_status_complete=task_status_complete,
                                     annotation_sort_key_func=annotation_sort_key_func)

        Path(output_image_file).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_image_file)

        logger.info(f"{str(output_image_file)} の生成完了")




    def write_semantic_segmentation_images2(self, annotation_zip: Path, default_input_data_size: InputDataSize,
                                           label_color_dict: Dict[str, RGB], output_dir: str,
                                           output_image_extension: str, task_status_complete: bool = False,
                                           annotation_sort_key_func: Optional[AnnotationSortKeyFunc] = None,
                                           sub_annotation_dir_list: Optional[List[str]] = None,
                                           str_background_color: Optional[str] = None):

        for parser in parse_simple_annotation_zip(annotation_zip):
            image = PIL.Image.new(mode="RGB", size=default_input_data_size, color=str_background_color)
            draw = PIL.ImageDraw.Draw(image)

            fill_annotation(parser, label_color_dict, draw)


        Path(output_image_file).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_image_file)

        logger.info(f"{str(output_image_file)} の生成完了")

    def main(self, args):
        annofabcli.common.cli.load_logging_config_from_args(args)

        logger.debug(f"args: {args}")

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

        try:
            if args.label_order_file is not None:
                labels = annofabcli.utils.read_lines_except_blank_line(args.label_order_file)

                def annotation_sort_key_func(d: Annotation) -> int:
                    """d
                    labelの順にアノテーションlistをソートする関数
                    """
                    if d["label"] not in labels:
                        return -1

                    return labels.index(d["label"])
            else:
                annotation_sort_key_func = None

        except Exception as e:
            logger.error("--label_order_file のParseに失敗しました。")
            raise e

        try:
            self.write_semantic_segmentation_images(
                annotation_dir=args.annotation_dir, default_input_data_size=default_input_data_size,
                label_color_dict=label_color_dict, output_dir=args.output_dir,
                output_image_extension=args.image_extension,
                str_background_color=args.background_color)

        except Exception as e:
            logger.exception(e)
            raise e


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument('--annotation_dir', type=str, required=True, help='アノテーションzipを展開したディレクトリのパス')

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

    parser.set_defaults(subcommand_func=main)


def main(args):
    WriteAnnotationImage().main(args)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_annotation_image"

    subcommand_help = "アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"

    description = ("アノテーションzipを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。"
                   "矩形、ポリゴン、塗りつぶし、塗りつぶしv2が対象。"
                   "複数のアノテーションディレクトリを指定して、画像をマージすることもできる。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
