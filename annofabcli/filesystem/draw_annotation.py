from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas
from annofabapi.parser import lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLineWithoutWebapi,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.draw_annotation import (
    Color,
    DrawingOptions,
    draw_annotation_all,
)
from annofabcli.common.facade import TaskQuery

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `filesystem draw_annotation` コマンドは非推奨です。代わりに `annotation_zip render` コマンドを使用してください。"
    " `filesystem draw_annotation` コマンドは2027/01/01以降に廃止予定です。"
)


class DrawAnnotation(CommandLineWithoutWebapi):
    COMMON_MESSAGE = "annofabcli filesystem draw_annotation:"

    @staticmethod
    def _create_label_color(args_label_color: str) -> dict[str, Color]:
        label_color_dict = get_json_from_args(args_label_color)
        for label_name, color in label_color_dict.items():
            if isinstance(color, list):
                label_color_dict[label_name] = tuple(color)
        return label_color_dict

    def main(self) -> None:
        args = self.args

        default_image_size: tuple[int, int] | None = None
        if args.default_image_size is not None:
            default_image_size = annofabcli.common.cli.get_input_data_size(args.default_image_size)
            if default_image_size is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument '--default_image_size': フォーマットが不正です。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.default_image_size is None and args.input_data_id_csv is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} '--default_image_size'または'--input_data_id_csv'のいずれかは必須です。",
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
        # Simpleアノテーションの読み込み
        if annotation_path.is_file():
            iter_parser = lazy_parse_simple_annotation_zip(annotation_path)
        else:
            iter_parser = lazy_parse_simple_annotation_dir(annotation_path)

        input_data_id_relation_dict: dict[str, str] | None = None
        if args.input_data_id_csv is not None:
            df = pandas.read_csv(
                args.input_data_id_csv,
                sep=",",
                header=None,
                names=("input_data_id", "image_path"),
                dtype={"input_data_id": "string"},
            )
            input_data_id_relation_dict = dict(zip(df["input_data_id"], df["image_path"], strict=False))

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
            default_image_size=default_image_size,
        )


def main(args: argparse.Namespace) -> None:
    print(DEPRECATED_MESSAGE, file=sys.stderr)  # noqa: T201
    DrawAnnotation(args).main()


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
        "``--default_image_size`` を指定しないときは必須です。\n"
        "CSVのフォーマットは、「1列目:input_data_id, 2列目:画像ファイルのパス」です。\n"
        "詳細は https://annofab-cli.readthedocs.io/ja/latest/command_reference/filesystem/draw_annotation.html を参照してください。",
    )

    parser.add_argument("--default_image_size", type=str, help="デフォルトの画像サイズ。 ``--input_data_id_csv`` を指定しないときは必須です。\n(例) 1280x720")

    LABEL_COLOR_SAMPLE = {"dog": [255, 128, 64], "cat": "blue"}  # noqa: N806
    parser.add_argument(
        "--label_color",
        type=str,
        help=f"label_nameとRGBの関係をJSON形式で指定します。\n(例) ``{json.dumps(LABEL_COLOR_SAMPLE)}``\n``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
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

    DRAWING_OPTIONS_SAMPLE = {"line_width": 3}  # noqa: N806
    parser.add_argument(
        "--drawing_options",
        type=str,
        help=f"描画オプションをJSON形式で指定します。\n(例) ``{json.dumps(DRAWING_OPTIONS_SAMPLE)}``\n\n``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
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
    subcommand_name = "draw_annotation"

    subcommand_help = "[DEPRECATED] 画像にアノテーションを描画します。"

    description = f"{subcommand_help}\n{DEPRECATED_MESSAGE}"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
