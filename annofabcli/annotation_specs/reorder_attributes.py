from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_label_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.delete_attributes import get_target_attribute_by_name_and_label
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedAttributeReorder:
    """
    属性並び替え対象を既存アノテーション仕様に対して解決した結果。
    """

    target_label: Mapping[str, Any]
    """属性を並び替える対象ラベル。"""

    first_attributes: list[Mapping[str, Any]]
    """先頭に移動する属性一覧。"""


def validate_attribute_reorder_inputs(
    *,
    label_id: str | None,
    label_name_en: str | None,
    attribute_ids: Sequence[str] | None,
    attribute_name_ens: Sequence[str] | None,
) -> None:
    """
    属性並び替え入力を検証する。

    Args:
        label_id: 対象ラベルID
        label_name_en: 対象ラベル英語名
        attribute_ids: 先頭に移動する属性ID一覧
        attribute_name_ens: 先頭に移動する属性英語名一覧

    Raises:
        ValueError: 入力値の組み合わせが不正な場合
    """
    if (label_id is None) == (label_name_en is None):
        raise ValueError("対象ラベルは `label_id` または `label_name_en` のどちらか一方だけ指定してください。")

    if (attribute_ids is None) == (attribute_name_ens is None):
        raise ValueError("先頭に移動する属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    resolved_attribute_ids = [] if attribute_ids is None else list(attribute_ids)
    resolved_attribute_name_ens = [] if attribute_name_ens is None else list(attribute_name_ens)
    if len(resolved_attribute_ids) == 0 and len(resolved_attribute_name_ens) == 0:
        raise ValueError("先頭に移動する属性を1件以上指定してください。")

    duplicated_attribute_ids = duplicated_set(resolved_attribute_ids)
    if duplicated_attribute_ids:
        duplicated_text = ", ".join(sorted(duplicated_attribute_ids))
        raise ValueError(f"入力されたattribute_idに重複があります。 :: {duplicated_text}")

    duplicated_attribute_name_ens = duplicated_set(resolved_attribute_name_ens)
    if duplicated_attribute_name_ens:
        duplicated_text = ", ".join(sorted(duplicated_attribute_name_ens))
        raise ValueError(f"入力された属性名(英語)に重複があります。 :: {duplicated_text}")


def get_target_attribute_by_id_and_label(
    annotation_specs: Mapping[str, Any],
    *,
    attribute_id: str,
    label: Mapping[str, Any],
) -> Mapping[str, Any]:
    """
    指定ラベルに紐づく、指定IDの属性を返す。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_id: 対象属性ID
        label: 対象ラベル

    Returns:
        対象属性

    Raises:
        ValueError: 対象属性が存在しない場合、または対象ラベルに紐づいていない場合
    """
    if attribute_id not in label["additional_data_definitions"]:
        raise ValueError(f"属性が対象ラベルに紐づいていません。 :: attribute_id='{attribute_id}', label_name_en='{get_label_name_en(label)}'")

    matched_attributes = [attribute for attribute in annotation_specs["additionals"] if attribute["additional_data_definition_id"] == attribute_id]
    if len(matched_attributes) == 0:
        raise ValueError(f"属性情報が見つかりませんでした。 :: attribute_id='{attribute_id}'")
    return matched_attributes[0]


def resolve_attribute_reorder(
    annotation_specs: dict[str, Any],
    *,
    label_id: str | None,
    label_name_en: str | None,
    attribute_ids: Sequence[str] | None,
    attribute_name_ens: Sequence[str] | None,
) -> ResolvedAttributeReorder:
    """
    属性並び替え対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        label_id: 対象ラベルID
        label_name_en: 対象ラベル英語名
        attribute_ids: 先頭に移動する属性ID一覧
        attribute_name_ens: 先頭に移動する属性英語名一覧

    Returns:
        解決済み属性並び替え対象
    """
    validate_attribute_reorder_inputs(
        label_id=label_id,
        label_name_en=label_name_en,
        attribute_ids=attribute_ids,
        attribute_name_ens=attribute_name_ens,
    )
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

    if label_id is not None:
        target_label = cast(Mapping[str, Any], annotation_specs_accessor.get_label(label_id=label_id))
    else:
        assert label_name_en is not None
        target_label = cast(Mapping[str, Any], annotation_specs_accessor.get_label(label_name=label_name_en))

    if attribute_ids is not None:
        first_attributes = [get_target_attribute_by_id_and_label(annotation_specs, attribute_id=attribute_id, label=target_label) for attribute_id in attribute_ids]
    else:
        assert attribute_name_ens is not None
        first_attributes = [get_target_attribute_by_name_and_label(annotation_specs, attribute_name_en=attribute_name_en, label=target_label) for attribute_name_en in attribute_name_ens]

    return ResolvedAttributeReorder(target_label=target_label, first_attributes=first_attributes)


def create_comment_for_reorder_attributes(resolved_reorder: ResolvedAttributeReorder) -> str:
    """
    属性並び替え時のデフォルトコメントを生成する。

    Args:
        resolved_reorder: 解決済み属性並び替え対象

    Returns:
        アノテーション仕様変更コメント
    """
    attribute_names = [get_attribute_name_en(attribute) for attribute in resolved_reorder.first_attributes]
    return f"以下のラベルの属性を指定順で先頭に移動しました。\n対象ラベル: {get_label_name_en(resolved_reorder.target_label)}\n対象属性: {', '.join(attribute_names)}"


def create_confirm_message_for_reorder_attributes(resolved_reorder: ResolvedAttributeReorder) -> str:
    """
    属性並び替え前の確認メッセージを生成する。

    Args:
        resolved_reorder: 解決済み属性並び替え対象

    Returns:
        確認メッセージ
    """
    attribute_names = [get_attribute_name_en(attribute) for attribute in resolved_reorder.first_attributes]
    return (
        f"ラベル '{get_label_name_en(resolved_reorder.target_label)}' の属性({len(resolved_reorder.first_attributes)}件)を指定順で先頭に移動します。"
        f"対象属性={attribute_names}。指定しなかった属性は現在の順番を維持します。よろしいですか？"
    )


def build_request_body_for_reorder_attributes(
    annotation_specs: dict[str, Any],
    *,
    resolved_reorder: ResolvedAttributeReorder,
    comment: str | None,
) -> dict[str, Any]:
    """
    属性並び替え用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_reorder: 解決済み属性並び替え対象
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    target_label_id = resolved_reorder.target_label["label_id"]
    first_attribute_ids = [attribute["additional_data_definition_id"] for attribute in resolved_reorder.first_attributes]
    first_attribute_id_set = set(first_attribute_ids)

    for label in request_body["labels"]:
        if label["label_id"] != target_label_id:
            continue
        remaining_attribute_ids = [attribute_id for attribute_id in label["additional_data_definitions"] if attribute_id not in first_attribute_id_set]
        label["additional_data_definitions"] = first_attribute_ids + remaining_attribute_ids
        break

    if comment is None:
        comment = create_comment_for_reorder_attributes(resolved_reorder)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class ReorderAttributesMain(CommandLineWithConfirm):
    """
    ラベル内の属性を並び替える本体処理。
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

    def reorder_attributes(
        self,
        *,
        label_id: str | None,
        label_name_en: str | None,
        attribute_ids: Sequence[str] | None,
        attribute_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定ラベル内の属性を指定順で先頭に移動し、アノテーション仕様を更新する。

        Args:
            label_id: 対象ラベルID
            label_name_en: 対象ラベル英語名
            attribute_ids: 先頭に移動する属性ID一覧
            attribute_name_ens: 先頭に移動する属性英語名一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_reorder = resolve_attribute_reorder(
            old_annotation_specs,
            label_id=label_id,
            label_name_en=label_name_en,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
        )

        confirm_message = create_confirm_message_for_reorder_attributes(resolved_reorder)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_reorder_attributes(old_annotation_specs, resolved_reorder=resolved_reorder, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"ラベル '{get_label_name_en(resolved_reorder.target_label)}' の属性 {len(resolved_reorder.first_attributes)} 件を指定順で先頭に移動しました。")
        return True


class ReorderAttributes(CommandLine):
    """
    ラベル内の属性を並び替えるコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs reorder_attributes: error:"

    def main(self) -> None:
        args = self.args

        attribute_ids = get_list_from_args(args.attribute_id) if args.attribute_id is not None else None
        attribute_name_ens = get_list_from_args(args.attribute_name_en) if args.attribute_name_en is not None else None

        obj = ReorderAttributesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.reorder_attributes(
            label_id=args.label_id,
            label_name_en=args.label_name_en,
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``reorder_attributes`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument("--label_name_en", type=str, help="属性を並び替える対象ラベルの英語名。")
    label_group.add_argument("--label_id", type=str, help="属性を並び替える対象ラベルのlabel_id。")

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        nargs="+",
        help=("先頭に移動する属性の英語名。複数指定した場合は、指定した順番で先頭に移動します。指定しなかった属性は現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"),
    )
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        nargs="+",
        help=(
            "先頭に移動する属性のattribute_id。複数指定した場合は、指定した順番で先頭に移動します。"
            "指定しなかった属性は現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``reorder_attributes`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ReorderAttributes(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs reorder_attributes`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "reorder_attributes"
    subcommand_help = "アノテーション仕様のラベル内の属性を並び替えます。"
    description = "アノテーション仕様の指定ラベルに含まれる属性を指定順で先頭に移動します。指定しなかった属性は現在の順番を維持します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
