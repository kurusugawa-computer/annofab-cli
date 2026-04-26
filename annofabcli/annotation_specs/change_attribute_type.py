from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Mapping
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.utils import get_attribute_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

SUPPORTED_ATTRIBUTE_TYPE_CONVERSIONS: Mapping[str, frozenset[str]] = {
    "choice": frozenset({"select"}),
    "select": frozenset({"choice"}),
    "text": frozenset({"comment"}),
    "comment": frozenset({"text"}),
}
"""対応している属性種類の変換ルール。将来の変換追加はこの定数を更新する。"""

SUPPORTED_ATTRIBUTE_TYPES = sorted(set(SUPPORTED_ATTRIBUTE_TYPE_CONVERSIONS) | {target for targets in SUPPORTED_ATTRIBUTE_TYPE_CONVERSIONS.values() for target in targets})
"""変換先として指定できる属性種類一覧。"""


def resolve_target_attribute(
    annotation_specs_accessor: AnnotationSpecsAccessor,
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
) -> dict[str, Any]:
    """
    CLI引数で指定された属性IDまたは属性名から対象属性を取得する。

    Args:
        annotation_specs_accessor: アノテーション仕様アクセサ
        attribute_id: 指定された属性ID
        attribute_name_en: 指定された属性英語名

    Returns:
        対象属性

    Raises:
        ValueError: 属性指定が不正、属性が見つからない、または属性名が曖昧な場合
    """
    if (attribute_id is None) == (attribute_name_en is None):
        raise ValueError("対象属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    if attribute_id is not None:
        return annotation_specs_accessor.get_attribute(attribute_id=attribute_id)

    assert attribute_name_en is not None
    return annotation_specs_accessor.get_attribute(attribute_name=attribute_name_en)


def validate_attribute_type_conversion(*, current_type: str, target_type: str) -> None:
    """
    属性種類の変換がサポート対象か検証する。

    Args:
        current_type: 現在の属性種類
        target_type: 変更後の属性種類

    Raises:
        ValueError: 同一種類への変更、または未対応の変換が指定された場合
    """
    if current_type == target_type:
        raise ValueError("現在の属性種類と変更後の属性種類が同じです。")

    allowed_target_types = SUPPORTED_ATTRIBUTE_TYPE_CONVERSIONS.get(current_type, frozenset())
    if target_type not in allowed_target_types:
        raise ValueError(f"属性種類 '{current_type}' から '{target_type}' への変更には対応していません。")


def create_comment_for_change_attribute_type(*, attribute_name_en: str, current_type: str, target_type: str) -> str:
    """
    属性種類変更時のデフォルトコメントを生成する。

    Args:
        attribute_name_en: 対象属性の英語名
        current_type: 変更前の属性種類
        target_type: 変更後の属性種類

    Returns:
        アノテーション仕様変更コメント
    """
    return f"以下の属性の種類を変更しました。\n属性名(英語): {attribute_name_en}\n変更前: {current_type}\n変更後: {target_type}"


class ChangeAttributeTypeMain(CommandLineWithConfirm):
    """
    既存属性の種類を変更する本体処理。
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

    def change_attribute_type(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        attribute_type: str,
        comment: str | None = None,
    ) -> bool:
        """
        指定した属性の種類を変更して、アノテーション仕様を更新する。

        Args:
            attribute_id: 対象属性ID
            attribute_name_en: 対象属性英語名
            attribute_type: 変更後の属性種類
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)
        target_attribute = resolve_target_attribute(
            annotation_specs_accessor,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
        )
        current_type = target_attribute["type"]
        validate_attribute_type_conversion(current_type=current_type, target_type=attribute_type)

        resolved_attribute_id = target_attribute["additional_data_definition_id"]
        resolved_attribute_name_en = get_attribute_name_en(target_attribute)
        confirm_message = f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' の属性種類を '{current_type}' から '{attribute_type}' に変更します。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        for attribute in request_body["additionals"]:
            if attribute["additional_data_definition_id"] != resolved_attribute_id:
                continue
            attribute["type"] = attribute_type
            break

        if comment is None:
            comment = create_comment_for_change_attribute_type(
                attribute_name_en=resolved_attribute_name_en,
                current_type=current_type,
                target_type=attribute_type,
            )
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性名(英語)='{resolved_attribute_name_en}', 属性ID='{resolved_attribute_id}' の属性種類を '{current_type}' から '{attribute_type}' に変更しました。")
        return True


class ChangeAttributeType(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs change_attribute_type: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、属性種類変更処理を実行する。
        """
        args = self.args

        obj = ChangeAttributeTypeMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.change_attribute_type(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            attribute_type=args.attribute_type,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``change_attribute_type`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        help="種類を変更する対象属性の英語名。1個のみ指定できます。",
    )
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        help="種類を変更する対象属性の属性ID。1個のみ指定できます。",
    )

    parser.add_argument(
        "--attribute_type",
        type=str,
        required=True,
        choices=SUPPORTED_ATTRIBUTE_TYPES,
        help=("変更後の属性種類。現在対応している変換は以下のみです。\n* ``choice`` ↔ ``select``\n* ``text`` ↔ ``comment``"),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``change_attribute_type`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeAttributeType(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs change_attribute_type`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "change_attribute_type"
    subcommand_help = "アノテーション仕様の既存属性の種類を変更します。"
    description = "アノテーション仕様の既存属性1個に対して、許可されている組み合わせの範囲で属性種類を変更します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
