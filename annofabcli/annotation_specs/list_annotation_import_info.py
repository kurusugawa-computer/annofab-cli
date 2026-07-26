from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from annofabapi.models import Lang
from annofabapi.util.annotation_specs import InternationalizationMessage, get_message_with_lang
from pydantic import BaseModel, ConfigDict

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format

logger = logging.getLogger(__name__)


class AnnotationImportChoice(BaseModel):
    """annotation importで指定できる選択肢情報。"""

    model_config = ConfigDict(frozen=True)

    choice_name_en: str
    """選択肢名（英語）。"""


class AnnotationImportAttribute(BaseModel):
    """annotation importで指定できる属性情報。"""

    model_config = ConfigDict(frozen=True)

    attribute_name_en: str
    """属性名（英語）。"""
    attribute_type: str
    """属性の種類。"""
    choices: list[AnnotationImportChoice]
    """属性で指定できる選択肢情報。"""


class AnnotationImportLabel(BaseModel):
    """annotation importで指定できるラベル情報。"""

    model_config = ConfigDict(frozen=True)

    label_name_en: str
    """ラベル名（英語）。"""
    annotation_type: str
    """ラベルの種類。"""
    attributes: list[AnnotationImportAttribute]
    """ラベルに指定できる属性情報。"""


def create_annotation_import_info_list(annotation_specs_v3: dict[str, Any]) -> list[AnnotationImportLabel]:
    """アノテーション仕様からannotation import用の情報一覧を生成します。

    Args:
        annotation_specs_v3: APIから取得したアノテーション仕様情報（v3版）。

    Returns:
        annotation import用の情報一覧。
    """

    dict_attribute = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs_v3["additionals"]}

    def get_required_english_name(name: InternationalizationMessage) -> str:
        result = get_message_with_lang(name, lang=Lang.EN_US)
        if result is None:
            raise ValueError("アノテーション仕様に英語名が存在しません。")
        return result

    def create_choice_list(attribute: dict[str, Any]) -> list[AnnotationImportChoice]:
        return [
            AnnotationImportChoice(
                choice_name_en=get_required_english_name(choice["name"]),
            )
            for choice in attribute["choices"]
        ]

    def create_attribute_list(label: dict[str, Any]) -> list[AnnotationImportAttribute]:
        result = []
        for attribute_id in label["additional_data_definitions"]:
            attribute = dict_attribute[attribute_id]
            result.append(
                AnnotationImportAttribute(
                    attribute_name_en=get_required_english_name(attribute["name"]),
                    attribute_type=attribute["type"],
                    choices=create_choice_list(attribute),
                )
            )
        return result

    return [
        AnnotationImportLabel(
            label_name_en=get_required_english_name(label["label_name"]),
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

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(f"{history['updated_datetime']}のアノテーション仕様を出力します。 :: history_id='{history['history_id']}', comment='{history['comment']}'")
        return history["history_id"]

    def main(self) -> None:
        args = self.args

        if args.project_id is not None:
            if args.before is not None:
                history_id = self.get_history_id_from_before_index(args.project_id, args.before)
                if history_id is None:
                    print(  # noqa: T201
                        f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                        file=sys.stderr,
                    )
                    sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            else:
                history_id = args.history_id

            annotation_specs, _ = self.service.api.get_annotation_specs(args.project_id, query_params={"history_id": history_id, "v": "3"})

        elif args.annotation_specs_json_file is not None:
            with args.annotation_specs_json_file.open() as f:
                annotation_specs = json.load(f)

        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json_file'のどちらかを指定する必要があります。")

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

    old_annotation_specs_group = parser.add_mutually_exclusive_group()
    old_annotation_specs_group.add_argument(
        "--history_id",
        type=str,
        help=(
            "出力したいアノテーション仕様のhistory_idを指定してください。 "
            "history_idは ``annotation_specs list_history`` コマンドで確認できます。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    old_annotation_specs_group.add_argument(
        "--before",
        type=annofabcli.common.cli.non_negative_int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。  "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

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

    subcommand_help = "annotation import 用のラベル名、属性名、選択肢名、種類を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
