from __future__ import annotations

import argparse
import copy
import logging
import uuid
from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.models import DefaultAnnotationType
from annofabapi.plugin import ThreeDimensionAnnotationType

import annofabcli.common.cli
from annofabcli.annotation_specs.add_choice_attribute import create_name, get_label_name_en
from annofabcli.annotation_specs.color import RgbColor, hex_to_rgb
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnnotationTypeDetail:
    """
    ``--annotation_type`` に指定できる値の説明です。
    """

    value: str
    """``--annotation_type`` に指定する実値。"""

    description: str
    """アノテーション種類の日本語説明。"""

    available_project_types: str
    """このアノテーション種類を利用できるプロジェクト種別。"""


ANNOTATION_TYPE_DETAILS = [
    AnnotationTypeDetail(DefaultAnnotationType.BOUNDING_BOX.value, "矩形", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.SEGMENTATION.value, "塗りつぶし（インスタンスセグメンテーション用）", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.SEGMENTATION_V2.value, "塗りつぶしv2（セマンティックセグメンテーション用）", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.POLYGON.value, "ポリゴン（閉じた頂点集合）", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.POLYLINE.value, "ポリライン（開いた頂点集合）", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.POINT.value, "点", "画像プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.CLASSIFICATION.value, "全体分類", "画像プロジェクト / 動画プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.RANGE.value, "動画の区間", "動画プロジェクト"),
    AnnotationTypeDetail(DefaultAnnotationType.CUSTOM.value, "カスタム", "カスタムプロジェクト"),
    AnnotationTypeDetail(ThreeDimensionAnnotationType.BOUNDING_BOX.value, "3次元のバウンディングボックス", "3次元プロジェクト"),
    AnnotationTypeDetail(ThreeDimensionAnnotationType.INSTANCE_SEGMENT.value, "3次元のインスタンスセグメント", "3次元プロジェクト"),
    AnnotationTypeDetail(ThreeDimensionAnnotationType.SEMANTIC_SEGMENT.value, "3次元のセマンティックセグメント", "3次元プロジェクト"),
]
"""``--annotation_type`` に指定できる値と、その意味・対応プロジェクト。"""

ANNOTATION_TYPE_CHOICES = [detail.value for detail in ANNOTATION_TYPE_DETAILS]
"""``--annotation_type`` に指定できる値一覧。"""


def create_annotation_type_help() -> str:
    """
    ``--annotation_type`` オプションのヘルプ文字列を生成する。

    Returns:
        引数ヘルプ文字列
    """
    lines = ["追加するラベルのアノテーション種類。", "", "指定できる値:"]
    lines.extend(f" * {detail.value} : {detail.description} [{detail.available_project_types} で使用可]" for detail in ANNOTATION_TYPE_DETAILS)
    return "\n".join(lines)


AUTO_COLOR_PALETTE_HEX: list[str] = [
    "#FF0000",  # 赤 (red)
    "#FF5500",  # オレンジ (orange)
    "#FFAA00",  # アンバー (amber)
    "#FFFF00",  # 黄 (yellow)
    "#AAFF00",  # 黄緑 (lime)
    "#55FF00",  # シャルトリューズ (chartreuse)
    "#00FF00",  # 緑 (green)
    "#00FF55",  # スプリンググリーン (spring green)
    "#00FFAA",  # ターコイズ (turquoise)
    "#00FFFF",  # シアン (cyan)
    "#00AAFF",  # スカイブルー (sky blue)
    "#0055FF",  # アジュール (azure)
    "#0000FF",  # 青 (blue)
    "#5500FF",  # インディゴ (indigo)
    "#AA00FF",  # バイオレット (violet)
    "#FF00FF",  # マゼンタ (magenta)
    "#FF00AA",  # ローズ (rose)
    "#FF0055",  # ピンクレッド (pink red)
    "#FFFFFF",  # 白 (white)
    "#C0C0C0",  # ライトグレー (light gray)
    "#808080",  # グレー (gray)
]
"""自動色選択で優先する高彩度のカラーパレット。"""


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


def create_auto_color(colors: Collection[RgbColor]) -> RgbColor:
    """
    AUTO_COLOR_PALETTE_HEX の中から使用回数が最も少ない色を返す。

    Args:
        colors: 既存色一覧

    Returns:
        Annofab API向けのRGB辞書
    """
    palette_color_tuples = [(color["red"], color["green"], color["blue"]) for color in map(hex_to_rgb, AUTO_COLOR_PALETTE_HEX)]
    color_counts: Counter[tuple[int, int, int]] = Counter()
    for color in colors:
        color_tuple = (color["red"], color["green"], color["blue"])
        if color_tuple in palette_color_tuples:
            color_counts[color_tuple] += 1

    red, green, blue = min(palette_color_tuples, key=lambda color: color_counts[color])
    return {"red": red, "green": green, "blue": blue}


def collect_label_colors(labels: Collection[dict[str, Any]]) -> list[RgbColor]:
    """
    既存ラベル一覧から色一覧を抽出する。

    Args:
        labels: 既存ラベル一覧

    Returns:
        既存色一覧
    """
    colors: list[RgbColor] = []
    for label in labels:
        color = label.get("color")
        if not isinstance(color, dict):
            continue
        colors.append({"red": color["red"], "green": color["green"], "blue": color["blue"]})
    return colors


def create_new_label(
    *,
    label_id: str,
    label_name_en: str,
    label_name_ja: str | None,
    annotation_type: str,
    color: RgbColor,
) -> dict[str, Any]:
    """
    新規ラベルのAnnofab API向けオブジェクトを生成する。

    Args:
        label_id: 新規ラベルID
        label_name_en: 新規ラベル英語名
        label_name_ja: 新規ラベル日本語名
        annotation_type: アノテーション種類
        color: Annofab API向けのRGB辞書

    Returns:
        Annofab API向けのラベルオブジェクト
    """
    return {
        "label_id": label_id,
        "label_name": create_name(label_name_en, label_name_ja),
        "annotation_type": annotation_type,
        "color": color,
        # 以下はキーが存在しないとAPIエラーになるため、空の値を入れておく
        "keybind": [],
        "field_values": {},
        "additional_data_definitions": [],
    }


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

        color = hex_to_rgb(color_code) if color_code is not None else create_auto_color(collect_label_colors(labels))
        new_label = create_new_label(
            label_id=generated_label_id,
            label_name_en=label_name_en,
            label_name_ja=label_name_ja,
            annotation_type=annotation_type,
            color=color,
        )

        confirm_message = f"ラベル名(英語)='{label_name_en}', label_id='{generated_label_id}', annotation_type='{annotation_type}' のラベルを追加します。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        request_body["labels"].append(new_label)

        if comment is None:
            comment = create_comment_from_label(label_name_en, annotation_type)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"ラベルを追加しました。 :: label_name_en='{label_name_en}', label_id='{generated_label_id}', annotation_type='{annotation_type}'")
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
    parser.add_argument("--annotation_type", type=str, required=True, choices=ANNOTATION_TYPE_CHOICES, help=create_annotation_type_help())
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
