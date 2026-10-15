from __future__ import annotations

import json
import logging
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from annofabapi.parser import SimpleAnnotationParser
from dataclasses_json import DataClassJsonMixin
from PIL import Image, ImageColor, ImageDraw

from annofabcli.common.facade import TaskQuery, match_annotation_with_task_query

logger = logging.getLogger(__name__)


Color = str | tuple[int, int, int]
IsParserFunc = Callable[[SimpleAnnotationParser], bool]


@dataclass(frozen=True)
class DrawingOptions(DataClassJsonMixin):
    line_width: int = 1
    """線の太さ[pixel]"""


class DrawingAnnotationForOneImage:
    _COLOR_PALETTE = [  # noqa: RUF012
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
        label_color_dict: dict[str, Color] | None = None,
        target_label_names: Collection[str] | None = None,
        polyline_labels: Collection[str] | None = None,
        drawing_options: DrawingOptions | None = None,
    ) -> None:
        self.label_color_dict = label_color_dict if label_color_dict is not None else {}
        self.target_label_names = set(target_label_names) if target_label_names is not None else None
        self.polyline_labels = set(polyline_labels) if polyline_labels is not None else None
        self.drawing_options = drawing_options if drawing_options is not None else DrawingOptions()
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
        draw: ImageDraw.ImageDraw,
        parser: SimpleAnnotationParser,
    ) -> ImageDraw.ImageDraw:
        """
        1個の入力データに属するアノテーションのみを描画する。

        Args:
            draw: draw: (IN/OUT) PillowのDrawing Object. 変更される。
            parser: Simple Annotationのparser

        Returns:
            アノテーションを描画した状態のDrawing Object
        """

        def draw_segmentation(data_uri: str, color: Color) -> None:
            # 外部ファイルを描画する
            with parser.open_outer_file(data_uri) as f:  # noqa: SIM117
                with Image.open(f) as outer_image:
                    draw.bitmap([0, 0], outer_image, fill=color)

        def draw_bounding_box(data: dict[str, Any], color: Color) -> None:
            xy = [
                (data["left_top"]["x"], data["left_top"]["y"]),
                (data["right_bottom"]["x"], data["right_bottom"]["y"]),
            ]
            draw.rectangle(xy, outline=color, width=self.drawing_options.line_width)

        def draw_single_point(data: dict[str, Any], color: Color, radius: int = 2) -> None:
            point_x = data["point"]["x"]
            point_y = data["point"]["y"]
            draw.ellipse([(point_x - radius, point_y - radius), (point_x + radius, point_y + radius)], fill=color)

        def draw_closed_polyline(data: dict[str, Any], color: Color) -> None:
            points = data["points"]
            first_point = points[0]
            xy = [(e["x"], e["y"]) for e in points] + [(first_point["x"], first_point["y"])]
            draw.line(xy, fill=color, width=self.drawing_options.line_width)

        def draw_polyline(data: dict[str, Any], color: Color) -> None:
            xy = [(e["x"], e["y"]) for e in data["points"]]
            draw.line(xy, fill=color, width=self.drawing_options.line_width)

        simple_annotation = parser.load_json()
        # 下層レイヤにあるアノテーションから順に画像化する
        # reversed関数を使う理由：`simple_annotation.details`は上層レイヤのアノテーションから順に格納されているため
        if self.target_label_names is not None:
            annotation_list = [e for e in reversed(simple_annotation["details"]) if e["label"] in self.target_label_names]
        else:
            annotation_list = list(reversed(simple_annotation["details"]))
        for annotation in annotation_list:
            data = annotation["data"]
            data_type = data["_type"]
            if data_type == "Classification":
                # 全体アノテーションなので描画できない
                continue

            label_name: str = annotation["label"]
            color = self.get_color(label_name)

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
                    draw_closed_polyline(data, color=color)

        return draw

    def main(
        self,
        parser: SimpleAnnotationParser,
        image_file: Path | None,
        output_file: Path,
        image_size: tuple[int, int] | None = None,
    ) -> None:
        """画像にアノテーションを描画したファイルを出力する。

        Args:
            parser (SimpleAnnotationParser): [description]
            image_file (Path): [description]
            output_file (Path): [description]
        """
        assert image_file is not None or image_size is not None

        if image_file is not None:
            with Image.open(image_file) as image:
                draw = ImageDraw.Draw(image)
                self._draw_annotations(draw, parser)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_file)

        elif image_size is not None:
            image = Image.new("RGBA", image_size, color="black")  # type: ignore[assignment]
            draw = ImageDraw.Draw(image)
            self._draw_annotations(draw, parser)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_file)


def create_is_target_parser_func(
    task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
) -> IsParserFunc | None:
    if task_ids is None and task_query is None:
        return None

    task_id_set = set(task_ids) if task_ids is not None else None

    def is_target_parser(parser: SimpleAnnotationParser) -> bool:
        if task_id_set is not None and len(task_id_set) > 0:  # noqa: SIM102
            if parser.task_id not in task_id_set:
                return False

        if task_query is not None:
            dict_simple_annotation = parser.load_json()
            if not match_annotation_with_task_query(dict_simple_annotation, task_query):
                return False

        return True

    return is_target_parser


def draw_annotation_all(  # noqa: PLR0913
    iter_parser: Iterator[SimpleAnnotationParser],
    image_dir: Path | None,
    input_data_id_relation_dict: dict[str, str] | None,
    output_dir: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    label_color_dict: dict[str, Color] | None = None,
    target_label_names: Collection[str] | None = None,
    polyline_labels: Collection[str] | None = None,
    drawing_options: DrawingOptions | None = None,
    default_image_size: tuple[int, int] | None = None,
) -> None:
    drawing = DrawingAnnotationForOneImage(
        label_color_dict=label_color_dict,
        target_label_names=target_label_names,
        polyline_labels=polyline_labels,
        drawing_options=drawing_options,
    )

    is_target_parser_func = create_is_target_parser_func(target_task_ids, task_query)

    total_count = 0
    success_count = 0

    for parser in iter_parser:
        logger.debug(f"{parser.json_file_path} を読み込みます。")
        if is_target_parser_func is not None and not is_target_parser_func(parser):
            continue

        total_count += 1
        input_data_id = parser.input_data_id
        if input_data_id_relation_dict is not None:  # noqa: SIM102
            if input_data_id not in input_data_id_relation_dict:
                logger.warning(f"input_data_id='{input_data_id}'に対応する画像ファイルのパスが見つかりませんでした。")
                continue

        image_file: Path | None = None
        if image_dir is not None and input_data_id_relation_dict is not None:
            image_file = image_dir / input_data_id_relation_dict[input_data_id]
            if not image_file.exists():
                logger.warning(f"input_data_id='{input_data_id}'に対応する画像ファイル'{image_file}'が見つかりませんでした。")
                continue

        json_file = Path(parser.json_file_path)
        if image_file is not None:
            output_file = output_dir / f"{json_file.parent.name}/{json_file.stem}{image_file.suffix}"
        else:
            output_file = output_dir / f"{json_file.parent.name}/{json_file.stem}.png"

        try:
            drawing.main(parser, image_file=image_file, output_file=output_file, image_size=default_image_size)
            logger.debug(f"{success_count + 1}件目: {output_file!s} を出力しました。image_file={image_file}, アノテーションJSON={parser.json_file_path}")
            success_count += 1
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"{parser.json_file_path} のアノテーションの描画に失敗しました。", exc_info=True)

    logger.info(f"{success_count} / {total_count} 件、アノテーションを描画しました。")

    new_label_color_dict = {label_name: ImageColor.getrgb(color) if isinstance(color, str) else color for label_name, color in drawing.label_color_dict.items()}
    logger.info(f"label_color={json.dumps(new_label_color_dict, ensure_ascii=False)}")
