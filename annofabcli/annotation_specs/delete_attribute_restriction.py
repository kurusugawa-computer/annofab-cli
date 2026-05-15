from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage
from annofabcli.annotation_specs.restriction_type import RESTRICTION_TYPE_TO_CONDITION_TYPE, matches_restriction_type
from annofabcli.annotation_specs.utils import get_target_attributes
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedRestrictionsForDelete:
    """
    削除対象の属性制約を解決した結果。
    """

    restrictions_to_remove: list[dict[str, Any]]
    """削除する属性制約一覧。"""

    restriction_text_list: list[str]
    """削除する属性制約のテキスト一覧。"""


def create_comment_for_delete_attribute_restriction(restriction_text_list: Collection[str]) -> str:
    """
    属性制約削除時のデフォルトコメントを生成する。

    Args:
        restriction_text_list: 削除する属性制約のテキスト一覧

    Returns:
        アノテーション仕様変更コメント
    """
    return "以下の属性制約を削除しました。\n" + "\n".join(restriction_text_list)


def create_confirm_message_for_delete_attribute_restriction(restriction_text_list: Collection[str]) -> str:
    """
    属性制約削除前の確認メッセージを生成する。

    Args:
        restriction_text_list: 削除する属性制約のテキスト一覧

    Returns:
        確認メッセージ
    """
    lines = [f"以下の属性制約({len(restriction_text_list)}件)を削除します。よろしいですか？"]
    lines.extend(f" * {restriction_text}" for restriction_text in restriction_text_list)
    return "\n".join(lines)


def resolve_restrictions_to_delete_by_json(
    annotation_specs: dict[str, Any],
    restrictions: list[dict[str, Any]],
) -> ResolvedRestrictionsForDelete:
    """
    JSON指定で削除する属性制約を解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        restrictions: 削除対象の属性制約一覧

    Returns:
        解決済み削除対象
    """
    old_restrictions = annotation_specs["restrictions"]
    message_obj = AttributeRestrictionMessage(
        labels=annotation_specs["labels"],
        additionals=annotation_specs["additionals"],
        raise_if_not_found=True,
    )

    restrictions_to_remove = []
    restriction_text_list = []
    for index, restriction in enumerate(restrictions):
        try:
            restriction_text = message_obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        except ValueError as e:
            logger.warning(f"{index + 1}件目 :: 次の属性制約は存在しないIDが含まれていたため、削除しません。 :: restriction=`{restriction}`, error_message=`{e!s}`")
            continue

        if restriction not in old_restrictions:
            logger.warning(f"{index + 1}件目 :: 次の属性制約は存在しないため、削除しません。 :: `{restriction_text}`")
            continue
        if restriction in restrictions_to_remove:
            logger.warning(f"{index + 1}件目 :: 次の属性制約は入力内で重複しているため、削除しません。 :: `{restriction_text}`")
            continue

        restrictions_to_remove.append(restriction)
        restriction_text_list.append(restriction_text)

    return ResolvedRestrictionsForDelete(
        restrictions_to_remove=restrictions_to_remove,
        restriction_text_list=restriction_text_list,
    )


def build_request_body_for_delete_attribute_restriction(
    annotation_specs: dict[str, Any],
    *,
    restrictions_to_remove: Collection[dict[str, Any]],
    restriction_text_list: Collection[str],
    comment: str | None,
) -> dict[str, Any]:
    """
    属性制約削除用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        restrictions_to_remove: 削除する属性制約一覧
        restriction_text_list: 削除する属性制約のテキスト一覧
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    request_body["restrictions"] = [restriction for restriction in request_body["restrictions"] if restriction not in restrictions_to_remove]
    if comment is None:
        comment = create_comment_for_delete_attribute_restriction(restriction_text_list)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


def resolve_restrictions_to_delete_by_attribute(
    annotation_specs: dict[str, Any],
    *,
    attribute_ids: Collection[str] | None,
    attribute_name_ens: Collection[str] | None,
    restriction_type: str | None = None,
) -> ResolvedRestrictionsForDelete:
    """
    属性指定で削除する属性制約を解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_ids: 対象属性ID一覧
        attribute_name_ens: 対象属性名(英語)一覧
        restriction_type: 削除対象の属性制約種類

    Returns:
        解決済み削除対象
    """
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attributes = get_target_attributes(
        annotation_specs_accessor,
        attribute_ids=attribute_ids,
        attribute_name_ens=attribute_name_ens,
    )
    target_attribute_ids = {attribute["additional_data_definition_id"] for attribute in target_attributes}
    message_obj = AttributeRestrictionMessage(
        labels=annotation_specs["labels"],
        additionals=annotation_specs["additionals"],
        raise_if_not_found=True,
    )

    restrictions_to_remove = [
        restriction
        for restriction in annotation_specs["restrictions"]
        if restriction["additional_data_definition_id"] in target_attribute_ids and matches_restriction_type(restriction, restriction_type)
    ]
    restriction_text_list = message_obj.get_restriction_text_list(restrictions_to_remove)
    return ResolvedRestrictionsForDelete(
        restrictions_to_remove=restrictions_to_remove,
        restriction_text_list=restriction_text_list,
    )


class DeleteAttributeRestrictionMain(CommandLineWithConfirm):
    """
    属性制約を削除する本体処理。
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

    def delete_restrictions_by_json(self, restrictions: list[dict[str, Any]], comment: str | None = None) -> bool:
        """
        指定したJSONと完全一致する属性制約を削除する。

        Args:
            restrictions: 削除対象の属性制約一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、更新が不要または確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_restrictions = resolve_restrictions_to_delete_by_json(old_annotation_specs, restrictions)

        if len(resolved_restrictions.restrictions_to_remove) == 0:
            logger.info("削除する属性制約はないため、アノテーション仕様を変更しません。")
            return False

        confirm_message = create_confirm_message_for_delete_attribute_restriction(resolved_restrictions.restriction_text_list)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_delete_attribute_restriction(
            old_annotation_specs,
            restrictions_to_remove=resolved_restrictions.restrictions_to_remove,
            restriction_text_list=resolved_restrictions.restriction_text_list,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_restrictions.restrictions_to_remove)} 件の属性制約を削除しました。")
        return True

    def delete_restrictions_by_attribute(
        self,
        *,
        attribute_ids: Collection[str] | None,
        attribute_name_ens: Collection[str] | None,
        restriction_type: str | None = None,
        comment: str | None = None,
    ) -> bool:
        """
        指定した属性に紐づく属性制約をすべて削除する。

        Args:
            attribute_ids: 対象属性ID一覧
            attribute_name_ens: 対象属性名(英語)一覧
            restriction_type: 削除対象の属性制約種類
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、更新が不要または確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_restrictions = resolve_restrictions_to_delete_by_attribute(
            old_annotation_specs,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            restriction_type=restriction_type,
        )
        if len(resolved_restrictions.restrictions_to_remove) == 0:
            logger.info("削除する属性制約はないため、アノテーション仕様を変更しません。")
            return False

        confirm_message = create_confirm_message_for_delete_attribute_restriction(resolved_restrictions.restriction_text_list)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_delete_attribute_restriction(
            old_annotation_specs,
            restrictions_to_remove=resolved_restrictions.restrictions_to_remove,
            restriction_text_list=resolved_restrictions.restriction_text_list,
            comment=comment,
        )
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_restrictions.restrictions_to_remove)} 件の属性制約を削除しました。")
        return True


class DeleteAttributeRestriction(CommandLine):
    """
    属性制約を削除するコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs delete_attribute_restriction: error:"

    def main(self) -> None:
        args = self.args
        obj = DeleteAttributeRestrictionMain(self.service, project_id=args.project_id, all_yes=args.yes)

        if args.restriction_json is not None:
            if args.restriction_type is not None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} --restriction_json を指定した場合、 --restriction_type は指定できません。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            restrictions = get_json_from_args(args.restriction_json)
            if not isinstance(restrictions, list):
                print(f"{self.COMMON_MESSAGE}: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            obj.delete_restrictions_by_json(restrictions, comment=args.comment)
            return

        attribute_ids = get_list_from_args(args.attribute_id) if args.attribute_id is not None else None
        attribute_name_ens = get_list_from_args(args.attribute_name_en) if args.attribute_name_en is not None else None
        obj.delete_restrictions_by_attribute(
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            restriction_type=args.restriction_type,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    target_group = parser.add_mutually_exclusive_group(required=True)

    sample_json = [
        {
            "additional_data_definition_id": "a1",
            "condition": {"value": "true", "_type": "Equals"},
        }
    ]
    target_group.add_argument(
        "--restriction_json",
        type=str,
        help=(
            "削除する属性制約情報のJSONを指定します。"
            "JSON形式は ``list_attribute_restriction --format json`` の出力と同じです。\n"
            f"(例) ``{json.dumps(sample_json)}``\n"
            "``file://`` を先頭に付けるとjsonファイルを指定できます。"
        ),
    )
    target_group.add_argument(
        "--attribute_id",
        type=str,
        nargs="+",
        help="指定した属性IDに紐づく属性制約をすべて削除します。1個だけ指定して ``file://`` を先頭に付けると、属性IDを1行ずつ記載したファイルを指定できます。",
    )
    target_group.add_argument(
        "--attribute_name_en",
        type=str,
        nargs="+",
        help="指定した属性名(英語)に紐づく属性制約をすべて削除します。1個だけ指定して ``file://`` を先頭に付けると、属性名(英語)を1行ずつ記載したファイルを指定できます。",
    )
    parser.add_argument(
        "--restriction_type",
        type=str,
        choices=list(RESTRICTION_TYPE_TO_CONDITION_TYPE.keys()),
        help=(
            "削除対象の属性制約種類。 ``--attribute_id`` または ``--attribute_name_en`` と併用したときだけ有効です。\n"
            "* ``can_input`` : 入力可否制約\n"
            "* ``has_label`` : ラベル条件制約\n"
            "* ``equals`` : 等価制約\n"
            "* ``not_equals`` : 非等価制約\n"
            "* ``matches`` : 正規表現一致制約\n"
            "* ``not_matches`` : 正規表現不一致制約\n"
            "* ``imply`` : 属性間の相関制約"
        ),
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete_attribute_restriction"

    subcommand_help = "アノテーション仕様の属性制約を削除します。"
    description = subcommand_help
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
