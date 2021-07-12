import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple, Union

import pandas
import PIL
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

import annofabcli
from annofabcli.common.cli import (
    AbstractCommandLineWithoutWebapiInterface,
    ArgumentParser,
    get_json_from_args,
    get_list_from_args,
)

logger = logging.getLogger(__name__)


Color = Union[str, Tuple[int, int, int]]


class DrawingAnnotationForOneImage:

    _COLOR_PALETTE = [
        "red",
        "maroon",
        "yellow",
        "olive",
        "lime",
        "green",
        "aqua",
        "teal",
        "blue",
        "navy",
        "fuchsia",
        "purple",
        "black",
        "gray",
        "silver",
        "white",
    ]

    def __init__(
        self,
        label_color_dict: Optional[Dict[str, Color]] = None,
        target_label_names: Optional[Iterator[str]] = None,
        polyline_labels: Optional[Iterator[str]] = None,
    ) -> None:
        self.label_color_dict = label_color_dict if label_color_dict is not None else {}
        self.target_label_names = set(target_label_names) if target_label_names is not None else None
        self.polyline_labels = set(polyline_labels) if polyline_labels is not None else None

        self._color_palette_index = 0

    def get_color(self, label_name: str) -> Color:
        if label_name in self.label_color_dict:
            return self.label_color_dict[label_name]
        else:
            color = self._COLOR_PALETTE[self._color_palette_index]
            self.label_color_dict[label_name] = color

            self._color_palette_index += 1
            self._color_palette_index = self._color_palette_index % len(self._COLOR_PALETTE)
            return color

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
        if self.target_label_names is not None:
            annotation_list = [e for e in reversed(simple_annotation["details"]) if e.label in self.target_label_names]
        else:
            annotation_list = list(reversed(simple_annotation["details"]))

        for annotation in annotation_list:
            data = annotation["data"]
            if data is None:
                # 画像全体アノテーション
                return draw

            label_name: str = annotation["label"]
            color = self.get_color(label_name)

            data_type = data["_type"]
            if data_type in {"SegmentationV2", "Segmentation"}:
                draw_segmentation(data["data_uri"], color=color)

            elif data_type == "BoundingBox":
                draw_bounding_box(data, color=color)

            elif data_type == "SinglePoint":
                draw_single_point(data, color=color)
            elif data_type == "Points":
                if self.polyline_labels is not None and label_name in self.polyline_labels:
                    draw_polyline(data, color=color)
                else:
                    draw_polygon(data, color=color)

        return draw

    def main(
        self,
        parser: SimpleAnnotationParser,
        image_file: Path,
        output_file: Path,
    ):
        with PIL.Image.open(image_file) as image:
            draw = PIL.ImageDraw.Draw(image)
            self._draw_annotations(draw, parser)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_file)


def draw_annotation_all(
    iter_parser: Iterator[SimpleAnnotationParser],
    image_dir: Path,
    input_data_id_relation_dict: Dict[str, str],
    output_dir: Path,
    *,
    label_color_dict: Optional[Dict[str, Color]] = None,
    target_label_names: Optional[Iterator[str]] = None,
):
    drawing = DrawingAnnotationForOneImage(label_color_dict=label_color_dict, target_label_names=target_label_names)
    total_count = 0
    success_count = 0
    for parser in iter_parser:
        logger.debug(f"{parser.json_file_path} を読み込みます。")
        # if is_target_parser_func is not None and not is_target_parser_func(parser):
        #     logger.debug(f"{parser.json_file_path} の画像化をスキップします。")
        #     continue
        total_count += 1
        input_data_id = parser.input_data_id
        if input_data_id not in input_data_id_relation_dict:
            logger.warning(f"input_data_id='{input_data_id}'に対応する画像ファイルのパスが見つかりませんでした。")
            continue

        image_file = image_dir / input_data_id_relation_dict[input_data_id]
        if not image_file.exists():
            logger.warning(f"input_data_id='{input_data_id}'に対応する画像ファイル'{image_file}'が見つかりませんでした。")
            continue

        output_file = output_dir / f"{Path(parser.json_file_path).stem}.{image_file.suffix}"

        try:
            drawing.main(parser, image_file=image_file, output_file=output_file)
            logger.debug(
                f"{success_count+1}件目: {str(output_file)} を出力しました。image_file={image_file}, アノテーションJSON={parser.json_file_path}"
            )
            success_count += 1
        except Exception as e:
            logger.warning(f"{parser.json_file_path} のアノテーションの描画に失敗しました。", e)

    return logger.info(f"{success_count} / {total_count} 件、アノテーションを描画しました。")


class DrawAnnotation(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args

        annotation_path: Path = args.annotation
        # Simpleアノテーションの読み込み
        if annotation_path.is_file():
            iter_parser = lazy_parse_simple_annotation_zip(annotation_path)
        else:
            iter_parser = lazy_parse_simple_annotation_dir(annotation_path)

        df = pandas.read_csv(
            args.input_data_id_csv,
            sep=",",
            header=None,
            names=("input_data_id", "image_path"),
        )
        input_data_id_relation_dict = {
            input_data_id: image_path for input_data_id, image_path in zip(df["input_data_id"], df["image_path"])
        }

        draw_annotation_all(
            iter_parser=iter_parser,
            image_dir=args.image_dir,
            input_data_id_relation_dict=input_data_id_relation_dict,
            output_dir=args.output_dir,
            label_color_dict=get_json_from_args(args.label_color),
            target_label_names=get_list_from_args(args.label_name),
        )


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
