from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, cast

from annofabapi.models import Lang
from annofabapi.util.annotation_specs import InternationalizationMessage, get_attribute_name_en, get_choice_name_en, get_label_name_en, get_message_with_lang
from pydantic import BaseModel, ConfigDict

import annofabcli.common.cli
from annofabcli.annotation_specs.history import add_history_arguments, load_annotation_specs_or_exit
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format

logger = logging.getLogger(__name__)


class AnnotationImportChoice(BaseModel):
    """annotation importで指定できる選択肢情報。"""

    model_config = ConfigDict(frozen=True)

    choice_name_en: str
    """選択肢名（英語）。"""
    choice_name_ja: str
    """選択肢名（日本語）。"""


class AnnotationImportAttribute(BaseModel):
    """annotation importで指定できる属性情報。"""

    model_config = ConfigDict(frozen=True)

    attribute_name_en: str
    """属性名（英語）。"""
    attribute_name_ja: str
    """属性名（日本語）。"""
    attribute_type: str
    """属性の種類。"""
    read_only: bool
    """読み込み専用の属性か否か。"""
    choices: list[AnnotationImportChoice]
    """属性で指定できる選択肢情報。"""


class AnnotationImportLabel(BaseModel):
    """annotation importで指定できるラベル情報。"""

    model_config = ConfigDict(frozen=True)

    label_name_en: str
    """ラベル名（英語）。"""
    label_name_ja: str
    """ラベル名（日本語）。"""
    annotation_type: str
    """ラベルの種類。"""
    attributes: list[AnnotationImportAttribute]
    """ラベルに指定できる属性情報。"""


def get_japanese_message(message: InternationalizationMessage) -> str:
    result = get_message_with_lang(message, Lang.JA_JP)
    assert result is not None
    return result


def create_annotation_import_info_list(annotation_specs_v3: dict[str, Any]) -> list[AnnotationImportLabel]:
    """アノテーション仕様からannotation import用の情報一覧を生成します。

    Args:
        annotation_specs_v3: APIから取得したアノテーション仕様情報（v3版）。

    Returns:
        annotation import用の情報一覧。
    """

    dict_attribute = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs_v3["additionals"]}

    def create_choice_list(attribute: dict[str, Any]) -> list[AnnotationImportChoice]:
        return [
            AnnotationImportChoice(
                choice_name_en=get_choice_name_en(choice),
                choice_name_ja=get_japanese_message(cast(InternationalizationMessage, choice["name"])),
            )
            for choice in attribute["choices"]
        ]

    def create_attribute_list(label: dict[str, Any]) -> list[AnnotationImportAttribute]:
        result = []
        for attribute_id in label["additional_data_definitions"]:
            attribute = dict_attribute[attribute_id]
            result.append(
                AnnotationImportAttribute(
                    attribute_name_en=get_attribute_name_en(attribute),
                    attribute_name_ja=get_japanese_message(cast(InternationalizationMessage, attribute["name"])),
                    attribute_type=attribute["type"],
                    read_only=attribute["read_only"],
                    choices=create_choice_list(attribute),
                )
            )
        return result

    return [
        AnnotationImportLabel(
            label_name_en=get_label_name_en(label),
            label_name_ja=get_japanese_message(cast(InternationalizationMessage, label["label_name"])),
            annotation_type=label["annotation_type"],
            attributes=create_attribute_list(label),
        )
        for label in annotation_specs_v3["labels"]
    ]


class PrintAnnotationImportInfo(CommandLine):
    """annotation import用のアノテーション仕様情報を出力します。"""

    COMMON_MESSAGE = "annofabcli annotation_specs list_annotation_import_info: error:"

    def print_annotation_import_info(self, annotation_specs_v3: dict[str, Any], output_format: OutputFormat, output: str | None = None) -> None:
        import_info_list = create_annotation_import_info_list(annotation_specs_v3)
        logger.info(f"{len(import_info_list)} 件のラベル情報を出力します。")
        print_according_to_format(
            [import_info.model_dump() for import_info in import_info_list],
            format=output_format,
            output=output,
        )

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

        self.print_annotation_import_info(annotation_specs, output_format=OutputFormat(args.format), output=args.output)


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
        choices=[OutputFormat.JSON.value, OutputFormat.PRETTY_JSON.value],
        default=OutputFormat.JSON.value,
        help="出力フォーマット",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PrintAnnotationImportInfo(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_annotation_import_info"

    subcommand_help = "アノテーションをimportする際に参照すべき情報（ラベル、属性、選択肢）のみを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
