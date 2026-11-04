from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import annofabapi

import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage
from annofabcli.annotation_specs.delete_attribute_restriction import (
    ResolvedRestrictionsForDelete,
    build_request_body_for_delete_attribute_restriction,
    create_confirm_message_for_delete_attribute_restriction,
)
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


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


class DeleteAttributeRestrictionPerRestrictionMain(CommandLineWithConfirm):
    """JSONで個別指定した属性制約を削除します。"""

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


class DeleteAttributeRestrictionPerRestriction(CommandLine):
    """JSONと完全一致する属性制約の削除コマンド。"""

    def main(self) -> None:
        """JSONで指定した属性制約だけを削除します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        restrictions = get_json_from_args(args.restriction_json)
        if not isinstance(restrictions, list):
            print("annofabcli annotation_specs delete_attribute_restriction_per_restriction: error: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        obj = DeleteAttributeRestrictionPerRestrictionMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.delete_restrictions_by_json(restrictions, comment=args.comment)


def main(args: argparse.Namespace) -> None:
    """認証して個別指定の属性制約削除を実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteAttributeRestrictionPerRestriction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """個別指定の属性制約削除の引数を定義します。

    Args:
        parser: 引数の追加先。

    Returns:
        None。
    """
    ArgumentParser(parser).add_project_id()
    sample = [{"additional_data_definition_id": "a1", "condition": {"value": "true", "_type": "Equals"}}]
    parser.add_argument(
        "--restriction_json",
        type=str,
        required=True,
        help="削除する属性制約のJSON配列。 ``list_attribute_restriction --format json`` と同じ形式です。 ``file://`` を先頭に付けるとJSONファイルを指定できます。" + f"\n(例) ``{json.dumps(sample)}``",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """個別指定の属性制約削除コマンドを登録します。

    Args:
        subparsers: コマンドの登録先。

    Returns:
        コマンドのパーサー。
    """
    help_message = "JSONで個別指定したアノテーション仕様の属性制約を削除します。"
    parser = annofabcli.common.cli.create_parser(
        subparsers, "delete_attribute_restriction_per_restriction", help_message, description=help_message, epilog="オーナーロールを持つユーザーで実行してください。"
    )
    parse_args(parser)
    return parser
