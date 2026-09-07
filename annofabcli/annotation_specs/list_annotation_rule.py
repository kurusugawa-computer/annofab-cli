from __future__ import annotations

import argparse
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, cast

from annofabapi.models import Lang
from annofabapi.util.annotation_specs import InternationalizationMessage, get_message_with_lang

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string

logger = logging.getLogger(__name__)


class AnnotationRuleLanguage(Enum):
    """アノテーションルールの出力言語。"""

    JA = "ja"
    EN = "en"


def get_message(message: InternationalizationMessage, language: AnnotationRuleLanguage) -> str:
    """指定言語のメッセージを取得し、存在しない場合は英語名を返します。"""

    lang = Lang.JA_JP if language == AnnotationRuleLanguage.JA else Lang.EN_US
    result = get_message_with_lang(message, lang)
    if result is not None:
        return result

    fallback = get_message_with_lang(message, Lang.EN_US)
    assert fallback is not None
    return fallback


def create_annotation_rule_text(annotation_specs_v3: dict[str, Any], language: AnnotationRuleLanguage) -> str:
    """アノテーション仕様から共有用のアノテーションルールをMarkdown形式で生成します。"""

    if language == AnnotationRuleLanguage.JA:
        title = "アノテーションルール"
        annotation_type_label = "アノテーションの種類"
        attributes_label = "属性"
        choices_label = "選択肢"
        no_attributes_label = "なし"
    else:
        title = "Annotation rules"
        annotation_type_label = "Annotation type"
        attributes_label = "Attributes"
        choices_label = "Choices"
        no_attributes_label = "None"

    attributes_by_id = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs_v3["additionals"]}
    lines = [f"# {title}"]

    for label in annotation_specs_v3["labels"]:
        label_name = get_message(cast(InternationalizationMessage, label["label_name"]), language)
        lines.extend(
            [
                "",
                f"## {label_name}",
                f"- {annotation_type_label}: `{label['annotation_type']}`",
            ]
        )

        attribute_ids = label["additional_data_definitions"]
        if len(attribute_ids) == 0:
            lines.append(f"- {attributes_label}: {no_attributes_label}")
            continue

        lines.append(f"- {attributes_label}:")
        for attribute_id in attribute_ids:
            attribute = attributes_by_id[attribute_id]
            attribute_name = get_message(cast(InternationalizationMessage, attribute["name"]), language)
            lines.append(f"  - {attribute_name}: `{attribute['type']}`")

            choices = attribute["choices"]
            if len(choices) == 0:
                continue

            lines.append(f"    - {choices_label}:")
            for choice in choices:
                choice_name = get_message(cast(InternationalizationMessage, choice["name"]), language)
                lines.append(f"      - {choice_name}")

    return "\n".join(lines)


class ListAnnotationRule(CommandLine):
    """共有用のアノテーションルールを出力します。"""

    COMMON_MESSAGE = "annofabcli annotation_specs list_annotation_rule: error:"
    """コマンドラインエラーの共通メッセージ。"""

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        """指定した相対位置のアノテーション仕様の履歴IDを取得します。"""

        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(f"{history['updated_datetime']}のアノテーション仕様を出力します。 :: history_id='{history['history_id']}', comment='{history['comment']}'")
        return history["history_id"]

    def main(self) -> None:
        """アノテーションルールを出力します。"""

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
            with args.annotation_specs_json_file.open(encoding="utf-8") as f:
                annotation_specs = json.load(f)
        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json_file'のどちらかを指定する必要があります。")

        annotation_rule_text = create_annotation_rule_text(annotation_specs, AnnotationRuleLanguage(args.lang))
        output_string(annotation_rule_text, args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を定義します。"""

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
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。 "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。 "
        ),
    )

    parser.add_argument(
        "--lang",
        type=str,
        choices=[language.value for language in AnnotationRuleLanguage],
        default=AnnotationRuleLanguage.JA.value,
        help="ラベル名、属性名、選択肢名の出力言語を指定します。",
    )
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """コマンドを実行します。"""

    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationRule(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """``list_annotation_rule`` 用のparserを生成します。"""

    subcommand_name = "list_annotation_rule"
    subcommand_help = "共有用にアノテーションルールを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
