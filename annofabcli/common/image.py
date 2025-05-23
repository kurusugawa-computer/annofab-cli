"""
アノテーション情報を画像化するメソッドです。
外部に公開しています。
"""

import logging
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

import PIL
import PIL.Image
import PIL.ImageDraw
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.exceptions import AnnotationOuterFileNotFoundError
from annofabapi.models import InputData
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
    draw: PIL.ImageDraw.ImageDraw,
    annotation: SimpleAnnotationDetail,
    label_color_dict: dict[str, RGB],
    outer_image: Optional[Any] = None,  # noqa: ANN401
) -> PIL.ImageDraw.ImageDraw:
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
        # Polygon or Polyline
        xy = [(e["x"], e["y"]) for e in data["points"]]
        draw.polygon(xy, fill=color)

    elif data_type in ["SegmentationV2", "Segmentation"]:
        # 塗りつぶしv2 or 塗りつぶし
        if outer_image is not None:
            draw.bitmap([0, 0], outer_image, fill=color)
        else:
            logger.warning(f"アノテーション種類が`{data_type}`ですが、`outer_image`がNoneです。 annotation_id='{annotation.annotation_id}'")

    return draw


def fill_annotation_list(
    draw: PIL.ImageDraw.ImageDraw,
    parser: SimpleAnnotationParser,
    label_color_dict: dict[str, RGB],
    label_name_list: Optional[list[str]] = None,
) -> PIL.ImageDraw.ImageDraw:
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
    simple_annotation = parser.parse()

    # 下層レイヤにあるアノテーションから順に画像化する
    # reversed関数を使う理由：`simple_annotation.details`は上層レイヤのアノテーションから順に格納されているため
    if label_name_list is not None:
        annotation_list = [elm for elm in reversed(simple_annotation.details) if elm.label in label_name_list]
    else:
        annotation_list = list(reversed(simple_annotation.details))

    for annotation in annotation_list:
        # 外部ファイルのImage情報を取得する
        data_uri_outer_image = get_data_uri_of_outer_file(annotation)
        if data_uri_outer_image is not None:
            try:
                with parser.open_outer_file(data_uri_outer_image) as f:
                    outer_image = PIL.Image.open(f)
                    # アノテーション情報を描画する
                    fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=outer_image)

            except AnnotationOuterFileNotFoundError as e:
                logger.warning(str(e))
                fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

        else:
            fill_annotation(draw=draw, annotation=annotation, label_color_dict=label_color_dict, outer_image=None)

    return draw


def write_annotation_image(  # noqa: ANN201
    parser: SimpleAnnotationParser,
    image_size: InputDataSize,
    label_color_dict: dict[str, RGB],
    output_image_file: Path,
    background_color: Optional[Any] = None,  # noqa: ANN401
    label_name_list: Optional[list[str]] = None,
):
    """
    JSONファイルに記載されているアノテーション情報を、画像化する。
    JSONファイルは、Annofabからダウンロードしたアノテーションzipに含まれるファイルを想定している。

    Notes:
        この関数はannofabcliのコードからは呼び出されていません。
        しかし、2023/03時点でこの関数を直接利用しているユーザーがいるので、この関数は削除せずに残しています。
        削除を検討するときは、作成者に確認してください。

    Args:
        parser: parser: Simple Annotationのparser
        image_size: 画像のサイズ. Tuple[width, height]
        label_color_dict: label_nameとRGBを対応付けたdict
        output_image_file: 出力先の画像ファイルのパス
        background_color: アノテーション画像の背景色.
            (ex) "rgb(173, 216, 230)", "#add8e6", "lightgray", (173,216,230)
            フォーマットは`ImageColor Module <https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html>`_
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))
        label_name_list: 画像化対象のlabel_name. Noneの場合は、すべてのlabel_nameが画像化対象です。

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

    fill_annotation_list(draw, parser, label_color_dict, label_name_list=label_name_list)

    output_image_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_image_file)


def write_annotation_grayscale_image(
    parser: SimpleAnnotationParser,
    image_size: InputDataSize,
    output_image_file: Path,
    label_name_list: Optional[list[str]] = None,
) -> None:
    """
    JSONファイルに記載されているアノテーション情報を、グレースケール(8bit 1channel)で画像化します。
    グレースケールの値は0〜255です。0が背景です。それ以外は`details`のlistの降順で 1〜255の値が割り当てられます。

    Notes:
        この関数はannofabcliのコードからは呼び出されていません。
        しかし、2023/03時点でこの関数を直接利用しているユーザーがいるので、この関数は削除せずに残しています。
        削除を検討するときは、作成者に確認してください。

    Args:
        parser: parser: Simple Annotationのparser
        image_size: 画像のサイズ. Tuple[width, height]
        output_image_file: 出力先の画像ファイルのパス
        label_name_list: 画像化対象のlabel_name. Noneの場合は、すべてのlabel_nameが画像化対象です。

    Raise:
        ValueError: `details`のlistの長さが255を超えている場合

    """
    image = PIL.Image.new(mode="L", size=image_size)
    draw = PIL.ImageDraw.Draw(image)

    simple_annotation = parser.load_json()

    # 下層レイヤにあるアノテーションから順に画像化する
    # reversed関数を使う理由：`simple_annotation.details`は上層レイヤのアノテーションから順に格納されているため
    if label_name_list is not None:
        annotation_list = [elm for elm in reversed(simple_annotation["details"]) if elm["label"] in set(label_name_list)]
    else:
        annotation_list = list(reversed(simple_annotation["details"]))

    # 描画対象のアノテーションを絞り込む
    annotation_list = [e for e in annotation_list if e["data"] is not None and e["data"]["_type"] in ["BoundingBox", "Points", "SegmentationV2", "Segmentation"]]

    if len(annotation_list) > 255:
        # channel depthは8bitなので、255個のアノテーションまでしか描画できない
        raise ValueError(f"アノテーションは255個までしか描画できません。アノテーションの数={len(annotation_list)}")

    color = 1
    for annotation in annotation_list:
        data = annotation["data"]
        data_type = annotation["data"]["_type"]
        if data_type == "BoundingBox":
            xy = [
                (data["left_top"]["x"], data["left_top"]["y"]),
                (data["right_bottom"]["x"], data["right_bottom"]["y"]),
            ]
            draw.rectangle(xy, fill=color)
            color += 1

        elif data_type == "Points":
            # Polygon or Polyline
            # 本当はPolylineのときは描画したくないのだが、Simple Annotationだけでは判断できないので、とりあえず描画する
            xy = [(e["x"], e["y"]) for e in data["points"]]
            draw.polygon(xy, fill=color)
            color += 1

        elif data_type in ["SegmentationV2", "Segmentation"]:
            # 塗りつぶしv2 or 塗りつぶし
            with parser.open_outer_file(data["data_uri"]) as f:
                outer_image = PIL.Image.open(f)
                draw.bitmap([0, 0], outer_image, fill=color)
                color += 1
        else:
            continue

    output_image_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_image_file)


def write_annotation_images_from_path(
    annotation_path: Path,
    label_color_dict: dict[str, RGB],
    output_dir_path: Path,
    image_size: Optional[InputDataSize] = None,
    input_data_dict: Optional[dict[str, InputData]] = None,
    output_image_extension: str = "png",
    background_color: Optional[Any] = None,  # noqa: ANN401
    label_name_list: Optional[list[str]] = None,
    is_target_parser_func: Optional[IsParserFunc] = None,
) -> bool:
    """
    Annofabからダウンロードしたアノテーションzipファイル、またはそのzipを展開したディレクトリから、アノテーション情報を画像化します。
    `image_size` or `input_data_dict` のいずれかを指定する必要があります。

    Args:
        annotation_path: Annofabからダウンロードしたアノテーションzipファイル、またはそのzipを展開したディレクトリのパス
        label_color_dict: label_nameとRGBを対応付けたdict. Key:label_name, Value: Tuple(R,G,B)
        output_dir_path: 画像の出力先のディレクトリのパス
        image_size: 画像のサイズ. Tuple[width, height]
        input_data_dict: 入力データのDict(key:input_data_id, value:InputData)
        output_image_extension: 出力する画像ファイルの拡張子. 指定しない場合は"png"です。
        background_color: アノテーション画像の背景色.
            (ex) "rgb(173, 216, 230)", "#add8e6", "lightgray", (173,216,230)
            フォーマットは`ImageColor Module <https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageColor.html>`_
            '指定しない場合は、黒（rgb(0,0,0)）になります。'))
        label_name_list: 画像化対象のlabel_name. Noneの場合は、すべてのlabel_nameが画像化対象です。
        is_target_parser_func: 画像化する条件を関数で指定できます。Noneの場合は、すべてを画像化します。関数の引数は`SimpleAnnotationParser`で、戻り値がbooleanです。戻り値がTrueならば画像化対象です。

    Returns:
        True: アノテーション情報の画像化に成功した。False: アノテーション情報の画像化に失敗した。

    """

    def _get_image_size(input_data_id: str) -> Optional[InputDataSize]:
        def _get_image_size_from_system_metadata(arg_input_data: dict[str, Any]):  # noqa: ANN202
            # 入力データの`input_data.system_metadata.original_resolution`を参照して、画像サイズを決める。
            original_resolution = arg_input_data["system_metadata"]["original_resolution"]
            if original_resolution is not None and (original_resolution.get("width") is not None and original_resolution.get("height") is not None):
                return original_resolution.get("width"), original_resolution.get("height")
            else:
                logger.warning(f"input_data_id='{input_data_id}'のプロパティ`system_metadata.original_resolution`には画像サイズが設定されていません。")
                return None

        if image_size is not None:
            return image_size
        elif input_data_dict is not None:
            input_data = input_data_dict.get(input_data_id)
            if input_data is None:
                logger.warning(f"input_data_id='{input_data_id}'の入力データは存在しなかったので、スキップします。")
                return None

            return _get_image_size_from_system_metadata(input_data)

        else:
            raise ValueError("引数`image_size`または`input_data_dict`のどちらかはnot Noneである必要があります。")

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
        tmp_image_size = _get_image_size(parser.input_data_id)
        if tmp_image_size is None:
            logger.warning(f"task_id='{parser.task_id}', input_data_id='{parser.input_data_id}': 画像サイズを取得できなかったので、スキップします。")
            continue

        write_annotation_image(
            parser,
            image_size=tmp_image_size,
            label_color_dict=label_color_dict,
            background_color=background_color,
            output_image_file=output_image_file,
            label_name_list=label_name_list,
        )
        logger.debug(f"画像ファイル '{output_image_file!s}' を生成しました。")
        count_created_image += 1

    logger.info(f"{output_dir_path!s} に、{count_created_image} 件の画像ファイルを生成しました。")
    return True
