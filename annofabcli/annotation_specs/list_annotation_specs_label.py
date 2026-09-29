from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.annotation_specs.color import rgb_to_hex
from annofabcli.annotation_specs.history import add_history_arguments, load_annotation_specs_or_exit
from annofabcli.common.annofab.annotation_specs import api_keybind_to_keybind, keybind_to_api_keybind, keybind_to_text
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


@dataclass
class FlattenLabel(DataClassJsonMixin):
    """
    ラベル情報を格納するクラスです。
    """

    label_id: str
    label_name_en: str | None
    label_name_ja: str | None
    label_name_vi: str | None
    annotation_type: str
    color: str
    """16進数カラーコード
    例: `#000000`
    """
    attribute_count: int
    """
    参照している属性の個数

    Notes:
        APIでは`additional_data_definitions`のような名前だが、分かりにくかったので"attribute"という名前に変えた。
    """
    keybind: dict[str, Any] | None
    """CLIで指定できる形式のキーバインド"""
    keybind_text: str | None
    """人が読める形式のキーバインド"""
    field_values: dict[str, Any]
    """ラベルに設定された field_values"""


def create_label_list(labels_v3: list[dict[str, Any]]) -> list[FlattenLabel]:
    """
    APIから取得したラベル情報（v3版）から、`FlattenLabel`のlistを生成します。

    Args:
        labels_v3: APIから取得したラベル情報（v3版）
    """

    def dict_label_to_dataclass(label: dict[str, Any]) -> FlattenLabel:
        """
        辞書のラベル情報をDataClassのラベル情報に変換します。
        """
        label_color = label["color"]
        hex_color_code = rgb_to_hex(label_color)
        additional_data_definitions = label["additional_data_definitions"]
        keybind = api_keybind_to_keybind(label.get("keybind", []))
        return FlattenLabel(
            label_id=label["label_id"],
            label_name_en=get_message_with_lang(label["label_name"], lang=Lang.EN_US),
            label_name_ja=get_message_with_lang(label["label_name"], lang=Lang.JA_JP),
            label_name_vi=get_message_with_lang(label["label_name"], lang=Lang.VI_VN),
            annotation_type=label["annotation_type"],
            color=hex_color_code,
            attribute_count=len(additional_data_definitions),
            keybind=keybind,
            keybind_text=keybind_to_text(keybind_to_api_keybind(keybind)) if keybind is not None else None,
            field_values=label.get("field_values", {}),
        )

    return [dict_label_to_dataclass(e) for e in labels_v3]


def create_label_list_for_csv(label_list: list[FlattenLabel]) -> list[dict[str, Any]]:
    """
    CSV出力用のラベル一覧を生成する。

    Args:
        label_list: ラベル一覧

    Returns:
        CSV出力用のラベル一覧
    """
    result = []
    for label in label_list:
        record = label.to_dict()
        record["keybind"] = "" if label.keybind is None else json.dumps(label.keybind, ensure_ascii=False)
        record["field_values"] = json.dumps(label.field_values, ensure_ascii=False)
        result.append(record)
    return result


class PrintAnnotationSpecsLabel(CommandLine):
    """
    アノテーション仕様を出力する
    """

    COMMON_MESSAGE = "annofabcli annotation_specs list_label: error:"

    def print_annotation_specs_label(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        label_list = create_label_list(annotation_specs_v3["labels"])
        if output_format == OutputFormat.CSV:
            columns = [
                "label_id",
                "label_name_en",
                "label_name_ja",
                "label_name_vi",
                "annotation_type",
                "color",
                "attribute_count",
                "keybind",
                "keybind_text",
                "field_values",
            ]
            df = pandas.DataFrame(create_label_list_for_csv(label_list), columns=columns)

            print_csv(df, output)

        elif output_format in [OutputFormat.JSON, OutputFormat.PRETTY_JSON]:
            annofabcli.common.utils.print_according_to_format([e.to_dict() for e in label_list], format=OutputFormat(output_format), output=output)

    def main(self) -> None:
        args = self.args
        annotation_specs = load_annotation_specs_or_exit(
            self.service,
            project_id=args.project_id,
            annotation_specs_json_file=args.annotation_specs_json_file,
            history_id=args.history_id,
            before=args.before,
            updated_datetime=args.updated_datetime,
            common_message=self.COMMON_MESSAGE,
        )

        self.print_annotation_specs_label(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    required_group = parser.add_mutually_exclusive_group(required=True)
    required_group.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に出力します。")
    required_group.add_argument(
        "--annotation_specs_json_file",
        type=Path,
        help="指定したアノテーション仕様のJSONファイルを指定します。JSONファイルに記載された情報を元に出力します。ただしアノテーション仕様の ``format_version`` は ``3`` である必要があります。",
    )

    add_history_arguments(parser)

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[OutputFormat.CSV.value, OutputFormat.JSON.value, OutputFormat.PRETTY_JSON.value],
        default=OutputFormat.CSV.value,
        help="出力フォーマット ",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationSpecsLabel(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_label"

    subcommand_help = "アノテーション仕様のラベル情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
