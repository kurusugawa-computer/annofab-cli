from __future__ import annotations

import argparse
import copy
import logging
import re
import uuid
from collections.abc import Collection
from typing import Any

import annofabapi
from annofabapi.models import DefaultAnnotationType
from annofabapi.plugin import ThreeDimensionAnnotationType

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import create_name, get_label_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


COLOR_PALETTE: list[tuple[int, int, int]] = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 255, 128),
]
ANNOTATION_TYPE_CHOICES = [e.value for e in DefaultAnnotationType] + [e.value for e in ThreeDimensionAnnotationType]


def parse_color(color_code: str) -> dict[str, int]:
    """
    16進数カラーコードをAnnofab API向けのRGB辞書へ変換する。

    Args:
        color_code: ``#RRGGBB`` 形式のカラーコード

    Returns:
        ``{"red": r, "green": g, "blue": b}``

    Raises:
        ValueError: 形式が ``#RRGGBB`` でない場合
    """
    hex_color_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
    if hex_color_pattern.fullmatch(color_code) is None:
        raise ValueError("`--color` には `#RRGGBB` 形式の16進数カラーコードを指定してください。")

    return {
        "red": int(color_code[1:3], 16),
        "green": int(color_code[3:5], 16),
        "blue": int(color_code[5:7], 16),
    }


def format_color(color: dict[str, Any]) -> str:
    """
    RGB辞書を16進数カラーコードへ変換する。

    Args:
        color: Annofab APIのRGB辞書

    Returns:
        ``#RRGGBB`` 形式のカラーコード
    """
    return f"#{color['red']:02X}{color['green']:02X}{color['blue']:02X}"


def create_comment_from_label(label_name_en: str, annotation_type: str) -> str:
    """
    ラベル追加時のデフォルトコメントを生成する。

    Args:
        label_name_en: 追加するラベルの英語名
        annotation_type: ラベルのアノテーション種類

    Returns:
        アノテーション仕様変更コメント
    """
    return f"以下のラベルを追加しました。\nラベル名(英語): {label_name_en}\nannotation_type: {annotation_type}"


def validate_new_label(labels: Collection[dict[str, Any]], *, label_id: str, label_name_en: str) -> None:
    """
    追加予定のラベルID・ラベル英語名が既存ラベルと衝突しないか検証する。

    Args:
        labels: 既存ラベル一覧
        label_id: 追加予定のラベルID
        label_name_en: 追加予定のラベル英語名

    Raises:
        ValueError: ラベルIDまたはラベル英語名が重複する場合
    """
    if any(label["label_id"] == label_id for label in labels):
        raise ValueError(f"label_id='{label_id}' のラベルは既に存在します。")

    if any(get_label_name_en(label) == label_name_en for label in labels):
        raise ValueError(f"label_name_en='{label_name_en}' のラベルは既に存在します。")


def create_auto_color(labels: Collection[dict[str, Any]]) -> dict[str, int]:
    """
    既存ラベルと重複しにくい色を決定的に生成する。

    Args:
        labels: 既存ラベル一覧

    Returns:
        Annofab API向けのRGB辞書
    """
    existing_colors = {(label["color"]["red"], label["color"]["green"], label["color"]["blue"]) for label in labels if isinstance(label.get("color"), dict)}

    for red, green, blue in COLOR_PALETTE:
        if (red, green, blue) not in existing_colors:
            return {"red": red, "green": green, "blue": blue}

    start_index = len(existing_colors)
    for offset in range(1, 4097):
        n = start_index + offset
        candidate = ((53 * n) % 256, (97 * n) % 256, (193 * n) % 256)
        if candidate not in existing_colors:
            return {"red": candidate[0], "green": candidate[1], "blue": candidate[2]}

    raise RuntimeError("自動生成する色を決定できませんでした。")


def create_new_label(
    *,
    sample_label: dict[str, Any] | None,
    label_id: str,
    label_name_en: str,
    label_name_ja: str | None,
    annotation_type: str,
    color: dict[str, int],
) -> dict[str, Any]:
    """
    新規ラベルのAnnofab API向けオブジェクトを生成する。

    Args:
        sample_label: 既存ラベルの代表サンプル。存在しない場合はNone
        label_id: 新規ラベルID
        label_name_en: 新規ラベル英語名
        label_name_ja: 新規ラベル日本語名
        annotation_type: アノテーション種類
        color: Annofab API向けのRGB辞書

    Returns:
        Annofab API向けのラベルオブジェクト
    """
    if sample_label is None:
        return {
            "label_id": label_id,
            "label_name": create_name(label_name_en, label_name_ja),
            "keybind": [],
            "annotation_type": annotation_type,
            "additional_data_definitions": [],
            "color": color,
            "metadata": {},
        }

    new_label = copy.deepcopy(sample_label)
    new_label["label_id"] = label_id
    new_label["label_name"] = create_name(label_name_en, label_name_ja)
    new_label["keybind"] = []
    new_label["annotation_type"] = annotation_type
    new_label["additional_data_definitions"] = []
    new_label["color"] = color
    new_label["metadata"] = {}

    if "field_values" in new_label:
        new_label["field_values"] = {}
    if "bounding_box_metadata" in new_label:
        new_label["bounding_box_metadata"] = None
    if "segmentation_metadata" in new_label:
        new_label["segmentation_metadata"] = None
    if "annotation_editor_feature" in new_label and isinstance(new_label["annotation_editor_feature"], dict):
        new_label["annotation_editor_feature"] = dict.fromkeys(new_label["annotation_editor_feature"], False)

    return new_label


class AddLabelMain(CommandLineWithConfirm):
    """
    ラベルをアノテーション仕様へ追加する本体処理。
    """

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.project_id = project_id
        CommandLineWithConfirm.__init__(self, all_yes)

    def add_label(
        self,
        *,
        label_name_en: str,
        annotation_type: str,
        label_id: str | None,
        label_name_ja: str | None,
        color_code: str | None,
        comment: str | None = None,
    ) -> bool:
        """
        ラベルを追加してアノテーション仕様を更新する。

        Args:
            label_name_en: 追加するラベルの英語名
            annotation_type: 追加するラベルのアノテーション種類
            label_id: 追加するラベルID。未指定ならUUIDv4を自動生成
            label_name_ja: 追加するラベルの日本語名
            color_code: ``#RRGGBB`` 形式のカラーコード
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        labels = old_annotation_specs["labels"]

        generated_label_id = label_id if label_id is not None else str(uuid.uuid4())
        validate_new_label(labels, label_id=generated_label_id, label_name_en=label_name_en)

        color = parse_color(color_code) if color_code is not None else create_auto_color(labels)
        new_label = create_new_label(
            sample_label=labels[0] if len(labels) > 0 else None,
            label_id=generated_label_id,
            label_name_en=label_name_en,
            label_name_ja=label_name_ja,
            annotation_type=annotation_type,
            color=color,
        )

        confirm_message = (
            f"ラベル名(英語)='{label_name_en}', label_id='{generated_label_id}', annotation_type='{annotation_type}', color='{format_color(color)}' のラベルを追加します。よろしいですか？"
        )
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        request_body["labels"].append(new_label)

        if comment is None:
            comment = create_comment_from_label(label_name_en, annotation_type)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"ラベルを追加しました。 :: label_name_en='{label_name_en}', label_id='{generated_label_id}', annotation_type='{annotation_type}', color='{format_color(color)}'")
        return True


class AddLabel(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_label: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、ラベル追加処理を実行する。
        """
        args = self.args

        obj = AddLabelMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_label(
            label_name_en=args.label_name_en,
            annotation_type=args.annotation_type,
            label_id=args.label_id,
            label_name_ja=args.label_name_ja,
            color_code=args.color,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_label`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument("--label_name_en", type=str, required=True, help="追加するラベルの英語名。")
    parser.add_argument("--annotation_type", type=str, required=True, choices=ANNOTATION_TYPE_CHOICES, help="追加するラベルのアノテーション種類。")
    parser.add_argument("--label_id", type=str, help="追加するラベルのlabel_id。未指定の場合はUUIDv4を自動生成します。")
    parser.add_argument("--label_name_ja", type=str, help="追加するラベルの日本語名。未指定の場合は英語名と同じ値を使用します。")
    parser.add_argument("--color", type=str, help="追加するラベルの色。 ``#RRGGBB`` 形式の16進数カラーコードを指定してください。未指定の場合は自動設定されます。")
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_label`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddLabel(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_label`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_label"
    subcommand_help = "アノテーション仕様にラベルを追加します。"
    description = "アノテーション仕様にラベルを1件追加します。属性の紐付けは行いません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
