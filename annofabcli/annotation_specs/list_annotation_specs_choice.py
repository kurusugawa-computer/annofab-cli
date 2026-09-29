from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import Lang
from annofabapi.util.annotation_specs import get_english_message, get_message_with_lang
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.annotation_specs.history import add_history_arguments, load_annotation_specs_or_exit
from annofabcli.common.annofab.annotation_specs import api_keybind_to_keybind, keybind_to_api_keybind, keybind_to_text
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)


@dataclass
class FlattenChoice(DataClassJsonMixin):
    """
    CSV用の選択肢情報を格納するクラスです。
    """

    attribute_id: str
    """
    属性ID
    どの属性に属しているか分かるようにするため追加した。
    """

    attribute_name_en: str | None
    """
    属性名（英語）
    どの属性に属しているか分かるようにするため追加した。
    """

    attribute_type: str
    """属性の種類"""
    choice_id: str
    choice_name_en: str | None
    choice_name_ja: str | None
    choice_name_vi: str | None
    is_default: bool
    """初期値として設定されているかどうか"""
    keybind: dict[str, Any] | None
    """CLIで指定できる形式のキーバインド"""
    keybind_text: str | None
    """人が読める形式のキーバインド"""


def create_flatten_choice_list_from_additionals(additionals_v3: list[dict[str, Any]]) -> list[FlattenChoice]:
    """
    APIから取得した属性情報（v3版）から、選択肢情報の一覧を生成します。

    Args:
        additionals_v3: APIから取得した属性情報（v3版）
    """

    def dict_choice_to_dataclass(
        choice: dict[str, Any],
        additional: dict[str, Any],
    ) -> FlattenChoice:
        """
        辞書の選択肢情報をDataClassの選択肢情報に変換します。
        """
        attribute_id = additional["additional_data_definition_id"]
        additional_name = additional["name"]

        choice_id = choice["choice_id"]
        choice_name = choice["name"]
        is_default = additional["default"] == choice_id
        keybind = api_keybind_to_keybind(choice.get("keybind", []))
        return FlattenChoice(
            attribute_id=attribute_id,
            attribute_name_en=get_english_message(additional_name),
            attribute_type=additional["type"],
            choice_id=choice_id,
            choice_name_en=get_message_with_lang(choice_name, lang=Lang.EN_US),
            choice_name_ja=get_message_with_lang(choice_name, lang=Lang.JA_JP),
            choice_name_vi=get_message_with_lang(choice_name, lang=Lang.VI_VN),
            is_default=is_default,
            keybind=keybind,
            keybind_text=keybind_to_text(keybind_to_api_keybind(keybind)) if keybind is not None else None,
        )

    tmp_list = []
    for additional in additionals_v3:
        choices = additional["choices"]
        if len(choices) == 0:
            continue
        for choice in choices:
            tmp_list.append(dict_choice_to_dataclass(choice, additional))  # noqa: PERF401
    return tmp_list


class PrintAnnotationSpecsAttribute(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs list_choice: error:"

    def print_annotation_specs_choice(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        choice_list = create_flatten_choice_list_from_additionals(annotation_specs_v3["additionals"])
        logger.info(f"{len(choice_list)} 件の選択肢情報を出力します。")

        if output_format == OutputFormat.CSV:
            columns = [
                "attribute_id",
                "attribute_name_en",
                "attribute_type",
                "choice_id",
                "choice_name_en",
                "choice_name_ja",
                "choice_name_vi",
                "is_default",
                "keybind",
                "keybind_text",
            ]
            records = []
            for choice in choice_list:
                record = choice.to_dict()
                record["keybind"] = "" if choice.keybind is None else json.dumps(choice.keybind, ensure_ascii=False)
                records.append(record)
            df = pandas.DataFrame(records, columns=columns)
            print_csv(df, output)

        elif output_format in [OutputFormat.JSON, OutputFormat.PRETTY_JSON]:
            print_according_to_format([e.to_dict() for e in choice_list], format=output_format, output=output)

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

        self.print_annotation_specs_choice(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


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
    PrintAnnotationSpecsAttribute(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_choice"

    subcommand_help = "アノテーション仕様のドロップダウンまたはラジオボタン属性の選択肢情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
