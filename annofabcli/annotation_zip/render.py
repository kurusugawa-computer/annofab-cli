from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip
from dataclasses_json import DataClassJsonMixin
from PIL import Image, ImageColor, ImageDraw

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLineWithoutWebapi,
    get_json_from_args,
    get_list_from_args,
)
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


def read_input_data_id_csv(csv_path: Path) -> dict[str, str]:
    """input_data_idと画像ファイルパスの対応関係をCSVから読み込む。

    Args:
        csv_path: ヘッダ行ありCSVのパス。

    Returns:
        input_data_idをキー、画像ファイルパスを値にしたdict。
    """
    df = pandas.read_csv(csv_path, sep=",", dtype={"input_data_id": "string"})
    required_columns = {"input_data_id", "image_path"}
    if not required_columns.issubset(set(df.columns)):
        raise ValueError(f"CSVには {sorted(required_columns)} の列が必要です。")

    return dict(zip(df["input_data_id"], df["image_path"], strict=False))


def create_label_color_dict(label_list: object) -> dict[str, Color]:
    """``annotation_specs list_label`` のJSON出力からラベル色の辞書を生成する。

    Args:
        label_list: ``annotation_specs list_label --format json`` の出力。

    Returns:
        ラベル英語名と色の対応関係。

    Raises:
        TypeError: JSONの型が不正な場合。
        ValueError: ラベル英語名が空、または重複している場合。
    """
    if not isinstance(label_list, list):
        raise TypeError("JSON配列を指定してください。")

    result: dict[str, Color] = {}
    for index, label in enumerate(label_list, start=1):
        if not isinstance(label, dict):
            raise TypeError(f"{index}件目のラベルはJSONオブジェクトである必要があります。")

        label_name_en = label.get("label_name_en")
        if not isinstance(label_name_en, str) or label_name_en == "":
            raise ValueError(f"{index}件目のラベルに、空でない文字列の `label_name_en` を指定してください。")
        if label_name_en in result:
            raise ValueError(f"`label_name_en` が重複しています。 :: label_name_en='{label_name_en}'")

        color = label.get("color")
        if not isinstance(color, str):
            raise TypeError(f"{index}件目のラベルに、文字列の `color` を指定してください。")
        result[label_name_en] = color

    return result


class RenderAnnotation(CommandLineWithoutWebapi):
    COMMON_MESSAGE = "annofabcli annotation_zip render:"

    @staticmethod
    def _create_label_color(args_label_color: str) -> dict[str, Color]:
        label_list = get_json_from_args(args_label_color)
        try:
            return create_label_color_dict(label_list)
        except (TypeError, ValueError) as e:
            print(f"{RenderAnnotation.COMMON_MESSAGE} argument '--label_color': {e}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

    def main(self) -> None:
        args = self.args

        image_size: tuple[int, int] | None = None
        if args.image_size is not None:
            image_size = annofabcli.common.cli.get_input_data_size(args.image_size)
            if image_size is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument '--image_size': フォーマットが不正です。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.image_size is None and args.input_data_id_csv is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} '--image_size'または'--input_data_id_csv'のいずれかは必須です。",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.image_dir is None and args.input_data_id_csv is not None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument '--image_dir': '--input_data_id_csv'を指定したときは必須です。",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_path: Path = args.annotation
        if annotation_path.is_file():
            iter_parser = lazy_parse_simple_annotation_zip(annotation_path)
        else:
            iter_parser = lazy_parse_simple_annotation_dir(annotation_path)

        input_data_id_relation_dict: dict[str, str] | None = None
        if args.input_data_id_csv is not None:
            try:
                input_data_id_relation_dict = read_input_data_id_csv(args.input_data_id_csv)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument '--input_data_id_csv': {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        draw_annotation_all(
            iter_parser=iter_parser,
            image_dir=args.image_dir,
            input_data_id_relation_dict=input_data_id_relation_dict,
            output_dir=args.output_dir,
            target_task_ids=get_list_from_args(args.task_id) if args.task_id is not None else None,
            task_query=task_query,
            label_color_dict=self._create_label_color(args.label_color) if args.label_color is not None else None,
            target_label_names=get_list_from_args(args.label_name) if args.label_name is not None else None,
            polyline_labels=get_list_from_args(args.polyline_label) if args.polyline_label is not None else None,
            drawing_options=DrawingOptions.from_dict(get_json_from_args(args.drawing_options)) if args.drawing_options is not None else None,
            default_image_size=image_size,
        )


def main(args: argparse.Namespace) -> None:
    RenderAnnotation(args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=Path,
        required=True,
        help="Annofabからダウンロードしたアノテーションzip、またはzipを展開したディレクトリを指定してください。",
    )

    parser.add_argument("--image_dir", type=Path, help="画像が存在するディレクトリを指定してください。\n'--input_data_id_csv'を指定したときは必須です。")

    parser.add_argument(
        "--input_data_id_csv",
        type=Path,
        help="``input_data_id`` と ``--image_dir`` 配下の画像ファイルを紐付けたCSVを指定してください。\n"
        "``--image_size`` を指定しないときは必須です。\n"
        "CSVのフォーマットは、「ヘッダ行あり、input_data_id列: input_data_id, image_path列: 画像ファイルのパス」です。\n"
        "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation_zip/render.html を参照してください。",
    )

    parser.add_argument("--image_size", type=str, help="アノテーションのみを描画するときの画像サイズ。 ``--input_data_id_csv`` を指定しないときは必須です。\n(例) 1280x720")

    parser.add_argument(
        "--label_color",
        type=str,
        help=(
            "ラベルの色をJSON配列で指定します。 ``annotation_specs list_label --format json`` の出力を指定できます。"
            " 各要素には ``label_name_en`` と ``color`` が必要です。"
            "\n``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-o",
        "--output_dir",
        type=Path,
        required=True,
        help="出力先ディレクトリのパスを指定してください。ディレクトリの構造はアノテーションzipと同じです。",
    )

    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        required=False,
        help=(
            "描画対象のアノテーションのlabel_nameを指定します。"
            "指定しない場合は、すべてのlabel_nameが描画対象になります。"
            " ``file://`` を先頭に付けると、label_name の一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.add_argument(
        "--polyline_label",
        type=str,
        nargs="+",
        required=False,
        help=(
            "ポリラインのlabel_nameを指定してください。"
            "2021/07時点ではアノテーションzipからポリラインかポリゴンか判断できないため、コマンドライン引数からポリラインのlabel_nameを指定する必要があります。"
            " ``file://`` を先頭に付けると、label_name の一覧が記載されたファイルを指定できます。"
            " \n【注意】アノテーションzipでポリラインかポリゴンかを判断できるようになれば、このオプションは削除する予定です。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    drawing_options_sample = {"line_width": 3}
    parser.add_argument(
        "--drawing_options",
        type=str,
        help=f"描画オプションをJSON形式で指定します。\n(例) ``{json.dumps(drawing_options_sample)}``\n\n``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    argument_parser.add_task_id(
        required=False,
        help_message=("描画対象であるタスクのtask_idを指定します。指定しない場合、すべてのタスクに含まれるアノテーションが描画されます。"),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="描画対象のタスクを絞り込むためのクエリ条件をJSON形式で指定します。\n"
        "使用できるキーは task_id, status, phase, phase_stage です。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "render"
    subcommand_help = "アノテーションzip内のアノテーションを画像として出力します。"
    description = "アノテーションzip内のアノテーションを画像として出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
