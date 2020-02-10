"""
アノテーション情報を画像化するメソッドです。
外部に公開しています。
"""
import logging
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import PIL
import PIL.Image
import PIL.ImageDraw
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.exceptions import AnnotationOuterFileNotFoundError
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

from annofabcli.common.typing import RGB, InputDataSize

logger = logging.getLogger(__name__)

IsParserFunc = Callable[[SimpleAnnotationParser], bool]
"""アノテーションparserに対してboolを返す関数"""


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


def fill_annotation(
    draw: PIL.ImageDraw.Draw,
    annotation: SimpleAnnotationDetail,
    label_color_dict: Dict[str, RGB],
    outer_image: Optional[Any] = None,
) -> PIL.ImageDraw.Draw:
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
        logger.warning(f"label_name = {annotation.label} のcolorが指定されていません。")
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
            logger.warning(
                f"アノテーション種類が`{data_type}`ですが、`outer_image`がNoneです。 " f"annotation_id={annotation.annotation_id}"
            )

    return draw


def fill_annotation_list(
    draw: PIL.ImageDraw.Draw, parser: SimpleAnnotationParser, label_color_dict: Dict[str, RGB]
) -> PIL.ImageDraw.Draw:
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
                    fill_annotation(
                        draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=outer_image
                    )

            except AnnotationOuterFileNotFoundError as e:
                logger.warning(str(e))
                fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

        else:
            fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

    return draw


def write_annotation_image(
    parser: SimpleAnnotationParser,
    image_size: InputDataSize,
    label_color_dict: Dict[str, RGB],
    output_image_file: Path,
    background_color: Optional[Any] = None,
):
    """
    JSONファイルに記載されているアノテーション情報を、画像化する。
    JSONファイルは、AnnoFabからダウンロードしたアノテーションzipに含まれるファイルを想定している。

    Args:
        parser: parser: Simple Annotationのparser
        image_size: 画像のサイズ. Tuple[width, height]
        label_color_dict: label_nameとRGBを対応付けたdict
        output_image_file: 出力先の画像ファイルのパス
        background_color: アノテーション画像の背景色.
            (ex) "rgb(173, 216, 230)", "#add8e6", "lightgray", (173,216,230)
            フォーマットは`ImageColor Module <https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html>`_  # noqa: E501
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))


    Examples:
        "simple-annotation.json" を読み込み、"out.png"画像を生成する。


            from pathlib import Path
            from annofabapi.parser import SimpleAnnotationDirParser
            parser = SimpleAnnotationDirParser( "simple-annotation.json")
            label_color_dict = {"dog": (255,0,0), "bird": (0,255,0)}
            write_annotation_image(parser=parser, image_size=(64,64), label_color_dict=label_color_dict,
                               output_image_file=Path("out.png"), background_color=(64,64,64))

    """

    image = PIL.Image.new(mode="RGB", size=image_size, color=background_color)
    draw = PIL.ImageDraw.Draw(image)

    fill_annotation_list(draw, parser, label_color_dict)

    output_image_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_image_file)


def write_annotation_images_from_path(
    annotation_path: Path,
    image_size: InputDataSize,
    label_color_dict: Dict[str, RGB],
    output_dir_path: Path,
    output_image_extension: str = "png",
    background_color: Optional[Any] = None,
    is_target_parser_func: Optional[IsParserFunc] = None,
) -> bool:
    """
    AnnoFabからダウンロードしたアノテーションzipファイル、またはそのzipを展開したディレクトリから、アノテーション情報を画像化します。


    Args:
        annotation_path: AnnoFabからダウンロードしたアノテーションzipファイル、またはそのzipを展開したディレクトリのパス
        image_size: 画像のサイズ. Tuple[width, height]
        label_color_dict: label_nameとRGBを対応付けたdict. Key:label_name, Value: Tuple(R,G,B)
        output_dir_path: 画像の出力先のディレクトリのパス
        output_image_extension: 出力する画像ファイルの拡張子. 指定しない場合は"png"です。
        background_color: アノテーション画像の背景色.
            (ex) "rgb(173, 216, 230)", "#add8e6", "lightgray", (173,216,230)
            フォーマットは`ImageColor Module <https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html>`_  # noqa: E501
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))
        is_target_parser_func: 画像化する条件を関数で指定できます。None場合は、すべてを画像化します。関数の引数は`SimpleAnnotationParser`で、戻り値がbooleanです。戻り値がTrueならば画像化対象です。

    Returns:
        True: アノテーション情報の画像化に成功した。False: アノテーション情報の画像化に失敗した。

    """

    if not annotation_path.exists():
        logger.warning(f"annotation_path: '{annotation_path}' は存在しません。")
        return False

    if annotation_path.is_dir():
        iter_lazy_parser = lazy_parse_simple_annotation_dir(annotation_path)
    elif zipfile.is_zipfile(str(annotation_path)):
        iter_lazy_parser = lazy_parse_simple_annotation_zip(annotation_path)
    else:
        logger.warning(f"annotation_path: '{annotation_path}' は、zipファイルまたはディレクトリではありませんでした。")
        return False

    count_created_image = 0
    for parser in iter_lazy_parser:
        logger.debug(f"{parser.json_file_path} を読み込みます。")
        if is_target_parser_func is not None and not is_target_parser_func(parser):
            logger.debug(f"{parser.json_file_path} の画像化をスキップします。")
            continue

        output_image_file = output_dir_path / f"{Path(parser.json_file_path).stem}.{output_image_extension}"
        write_annotation_image(
            parser,
            image_size=image_size,
            label_color_dict=label_color_dict,
            background_color=background_color,
            output_image_file=output_image_file,
        )
        logger.debug(f"画像ファイル '{str(output_image_file)}' を生成しました。")
        count_created_image += 1

    logger.info(f"{str(output_dir_path)} に、{count_created_image} 件の画像ファイルを生成しました。")
    return True
