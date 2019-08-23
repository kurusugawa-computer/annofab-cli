import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple  # pylint: disable=unused-import

import PIL
import PIL.Image
import PIL.ImageDraw
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.parser import SimpleAnnotationParser
from annofabapi.exceptions import AnnotationOuterFileNotFoundError

from annofabcli.common.typing import RGB, InputDataSize

logger = logging.getLogger(__name__)


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


def fill_annotation(draw: PIL.ImageDraw.Draw, annotation: SimpleAnnotationDetail, label_color_dict: Dict[str, RGB],
                    outer_image: Optional[Any] = None) -> PIL.ImageDraw.Draw:
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
        logger.warning(f"label_name = {annotation['label']} のcolorが指定されていません。")
        color = (255, 255, 255)

    data_type = data["_type"]
    if data_type == "BoundingBox":
        xy = [(data["left_top"]["x"], data["left_top"]["y"]), (data["right_bottom"]["x"], data["right_bottom"]["y"])]
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
            logger.warning(f"アノテーション種類が`{data_type}`ですが、`outer_image`がNoneです。 "
                           f"annotation_id={annotation.annotation_id}")

    return draw


def fill_annotation_list(draw: PIL.ImageDraw.Draw, parser: SimpleAnnotationParser,
                         label_color_dict: Dict[str, RGB]) -> PIL.ImageDraw.Draw:
    """
    1個の入力データに属するアノテーションlistを描画する

    Args:
        draw: draw: (IN/OUT) PillowのDrawing Object. 変更される。
        parser: Simple Annotationのparser
        label_color_dict: label_nameとRGBを対応付けたdict

    Returns:
        アノテーションを描画した状態のDrawing Object
    """
    simple_annotation = parser.parse()

    for annotation in reversed(simple_annotation.details):
        # 外部ファイルのImage情報を取得する
        data_uri_outer_image = get_data_uri_of_outer_file(annotation)
        if data_uri_outer_image is not None:
            try:
                with parser.open_outer_file(data_uri_outer_image) as f:
                    outer_image = PIL.Image.open(f)
                    # アノテーション情報を描画する
                    fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict,
                                    outer_image=outer_image)

            except AnnotationOuterFileNotFoundError as e:
                logger.warning(str(e))
                fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

        else:
            fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

    return draw


def write_annotation_image(parser: SimpleAnnotationParser, image_size: InputDataSize, label_color_dict: Dict[str, RGB],
                           output_image_file: Path, background_color: Optional[Any] = None):
    """
    JSONファイルに記載されているアノテーション情報を、画像化する。
    JSONファイルは、AnnoFabからダウンロードしたアノテーションzipに含まれるファイルを想定している。

    Args:
        parser: parser: Simple Annotationのparser
        image_size: 画像のサイズ. Tuple[width, height]
        parser: annotationの遅延Parser
        label_color_dict: label_nameとRGBを対応付けたdict
        output_image_file: 出力先の画像ファイルのパス
        background_color: アノテーション画像の背景色.
            (ex) "rgb(173, 216, 230)", "#add8e6", "lightgray", (173,216,230)
            フォーマットは`ImageColor Module <https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html>`_  # noqa: E501
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))


    Examples:

    """

    image = PIL.Image.new(mode="RGB", size=image_size, color=background_color)
    draw = PIL.ImageDraw.Draw(image)

    fill_annotation_list(draw, parser, label_color_dict)

    output_image_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_image_file)
