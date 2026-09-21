from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, cast

from annofabapi.models import AdditionalDataDefinitionType, DefaultAnnotationType, Lang
from annofabapi.plugin import ThreeDimensionAnnotationType
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


class DescriptionLanguage(Enum):
    """ラベルと属性の説明文の出力言語。"""

    JA = "ja"
    EN = "en"


ANNOTATION_TYPE_DISPLAY_NAMES: Mapping[str, Mapping[DescriptionLanguage, str]] = {
    DefaultAnnotationType.BOUNDING_BOX.value: {DescriptionLanguage.JA: "矩形", DescriptionLanguage.EN: "Bounding box"},
    DefaultAnnotationType.SEGMENTATION.value: {DescriptionLanguage.JA: "インスタンスセグメンテーション", DescriptionLanguage.EN: "Instance segmentation"},
    DefaultAnnotationType.SEGMENTATION_V2.value: {DescriptionLanguage.JA: "セマンティックセグメンテーション", DescriptionLanguage.EN: "Semantic segmentation"},
    DefaultAnnotationType.POLYGON.value: {DescriptionLanguage.JA: "ポリゴン", DescriptionLanguage.EN: "Polygon"},
    DefaultAnnotationType.POLYLINE.value: {DescriptionLanguage.JA: "ポリライン", DescriptionLanguage.EN: "Polyline"},
    DefaultAnnotationType.POINT.value: {DescriptionLanguage.JA: "点", DescriptionLanguage.EN: "Point"},
    DefaultAnnotationType.CLASSIFICATION.value: {DescriptionLanguage.JA: "全体分類", DescriptionLanguage.EN: "Classification"},
    DefaultAnnotationType.RANGE.value: {DescriptionLanguage.JA: "動画の区間", DescriptionLanguage.EN: "Video range"},
    DefaultAnnotationType.CUSTOM.value: {DescriptionLanguage.JA: "カスタム", DescriptionLanguage.EN: "Custom"},
    ThreeDimensionAnnotationType.BOUNDING_BOX.value: {DescriptionLanguage.JA: "3次元バウンディングボックス", DescriptionLanguage.EN: "3D bounding box"},
    ThreeDimensionAnnotationType.INSTANCE_SEGMENT.value: {DescriptionLanguage.JA: "3次元インスタンスセグメンテーション", DescriptionLanguage.EN: "3D instance segmentation"},
    ThreeDimensionAnnotationType.SEMANTIC_SEGMENT.value: {DescriptionLanguage.JA: "3次元セマンティックセグメンテーション", DescriptionLanguage.EN: "3D semantic segmentation"},
}
"""アノテーション種類の表示名。"""


ATTRIBUTE_TYPE_DISPLAY_NAMES: Mapping[str, Mapping[DescriptionLanguage, str]] = {
    AdditionalDataDefinitionType.FLAG.value: {DescriptionLanguage.JA: "チェックボックス", DescriptionLanguage.EN: "Checkbox"},
    AdditionalDataDefinitionType.INTEGER.value: {DescriptionLanguage.JA: "整数", DescriptionLanguage.EN: "Integer"},
    AdditionalDataDefinitionType.TEXT.value: {DescriptionLanguage.JA: "1行テキスト", DescriptionLanguage.EN: "Text"},
    AdditionalDataDefinitionType.COMMENT.value: {DescriptionLanguage.JA: "複数行テキスト", DescriptionLanguage.EN: "Comment"},
    AdditionalDataDefinitionType.CHOICE.value: {DescriptionLanguage.JA: "ラジオボタン", DescriptionLanguage.EN: "Radio button"},
    AdditionalDataDefinitionType.SELECT.value: {DescriptionLanguage.JA: "ドロップダウン", DescriptionLanguage.EN: "Dropdown"},
    AdditionalDataDefinitionType.TRACKING.value: {DescriptionLanguage.JA: "トラッキングID", DescriptionLanguage.EN: "Tracking ID"},
    AdditionalDataDefinitionType.LINK.value: {DescriptionLanguage.JA: "アノテーションリンク", DescriptionLanguage.EN: "Annotation link"},
}
"""属性種類の表示名。"""


def get_message(message: InternationalizationMessage, language: DescriptionLanguage) -> str:
    """指定言語のメッセージを取得する。

    指定言語の名前が存在しない場合は、英語名、日本語名の順に代替する。
    """

    target_lang = Lang.JA_JP if language == DescriptionLanguage.JA else Lang.EN_US
    for lang in (target_lang, Lang.EN_US, Lang.JA_JP):
        result = get_message_with_lang(message, lang)
        if result is not None:
            return result
    raise ValueError("ラベル名、属性名、または選択肢名が設定されていません。")


def get_display_name(value: str, display_names: Mapping[str, Mapping[DescriptionLanguage, str]], language: DescriptionLanguage) -> str:
    """値に対応する指定言語の表示名を取得する。"""

    localized_names = display_names.get(value)
    if localized_names is None:
        return value
    return localized_names[language]


def escape_markdown_text(value: str) -> str:
    """Markdownの構造に影響する文字をエスケープする。"""

    result = value.replace("\\", "\\\\").replace("\r", " ").replace("\n", " ")
    for character in ("`", "*", "{", "}", "[", "]", "<", ">", "#", "+", "-", "!", "|"):
        result = result.replace(character, f"\\{character}")
    return result


def create_label_attributes_description(annotation_specs_v3: Mapping[str, Any], language: DescriptionLanguage) -> str:
    """アノテーション仕様からラベルと属性の関係をMarkdown形式で生成する。"""

    if language == DescriptionLanguage.JA:
        label_template = "# 「{name}」ラベル（{annotation_type}）"
        attribute_template = "- 「{name}」属性（{attribute_type}{read_only}）"
        no_attributes = "- 属性なし"
        read_only = "、読み込み専用"
        no_labels = "ラベルはありません。"
    else:
        label_template = '# Label "{name}" ({annotation_type})'
        attribute_template = '- Attribute "{name}" ({attribute_type}{read_only})'
        no_attributes = "- No attributes"
        read_only = ", read-only"
        no_labels = "No labels."

    attributes_by_id = {attribute["additional_data_definition_id"]: attribute for attribute in annotation_specs_v3["additionals"]}
    lines: list[str] = []

    for label in annotation_specs_v3["labels"]:
        label_name = escape_markdown_text(get_message(cast(InternationalizationMessage, label["label_name"]), language))
        annotation_type = get_display_name(label["annotation_type"], ANNOTATION_TYPE_DISPLAY_NAMES, language)
        if len(lines) > 0:
            lines.append("")
        lines.extend([label_template.format(name=label_name, annotation_type=annotation_type), ""])

        attribute_ids = label["additional_data_definitions"]
        if len(attribute_ids) == 0:
            lines.append(no_attributes)
            continue

        for attribute_id in attribute_ids:
            attribute = attributes_by_id[attribute_id]
            attribute_name = escape_markdown_text(get_message(cast(InternationalizationMessage, attribute["name"]), language))
            attribute_type = get_display_name(attribute["type"], ATTRIBUTE_TYPE_DISPLAY_NAMES, language)
            read_only_text = read_only if attribute["read_only"] else ""
            lines.append(attribute_template.format(name=attribute_name, attribute_type=attribute_type, read_only=read_only_text))

            for choice in attribute["choices"]:
                choice_name = escape_markdown_text(get_message(cast(InternationalizationMessage, choice["name"]), language))
                lines.append(f"  - {choice_name}")

    return "\n".join(lines) if len(lines) > 0 else no_labels


class DescribeLabelAttributes(CommandLine):
    """ラベルと属性の関係を出力する。"""

    COMMON_MESSAGE = "annofabcli annotation_specs describe_label_attributes: error:"
    """コマンドラインエラーの共通メッセージ。"""

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        """指定した相対位置のアノテーション仕様の履歴IDを取得する。"""

        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        logger.info(f"{history['updated_datetime']}のアノテーション仕様を出力します。 :: history_id='{history['history_id']}', comment='{history['comment']}'")
        return history["history_id"]

    def main(self) -> None:
        """ラベルと属性の関係を出力する。"""

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
            if args.history_id is not None or args.before is not None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --history_id/--before: '--annotation_specs_json_file' を指定したときは指定できません。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            with args.annotation_specs_json_file.open(encoding="utf-8") as f:
                annotation_specs = json.load(f)
        else:
            raise RuntimeError("'--project_id'か'--annotation_specs_json_file'のどちらかを指定する必要があります。")

        description = create_label_attributes_description(annotation_specs, DescriptionLanguage(args.lang))
        output_string(description, args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を定義する。"""

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
            "指定しない場合は、最新のアノテーション仕様が出力されます。"
        ),
    )
    old_annotation_specs_group.add_argument(
        "--before",
        type=annofabcli.common.cli.non_negative_int,
        help=(
            "出力したい過去のアノテーション仕様が、最新よりいくつ前のアノテーション仕様であるかを指定してください。 "
            "たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を出力します。 "
            "指定しない場合は、最新のアノテーション仕様が出力されます。"
        ),
    )

    parser.add_argument(
        "--lang",
        type=str,
        choices=[language.value for language in DescriptionLanguage],
        default=DescriptionLanguage.JA.value,
        help="ラベル名、属性名、選択肢名の出力言語を指定します。",
    )
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """コマンドを実行する。"""

    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DescribeLabelAttributes(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """``describe_label_attributes`` 用のparserを生成する。"""

    subcommand_name = "describe_label_attributes"
    subcommand_help = "ラベルと属性の関係を共有用のMarkdown形式で出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
