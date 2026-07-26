from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_attribute_name_en, get_choice_name_en

import annofabcli.common.cli
from annofabcli.annotation_specs.delete_choices import get_target_choices
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedChoiceReorder:
    """
    選択肢並び替え対象を既存アノテーション仕様に対して解決した結果。
    """

    target_attribute: Mapping[str, Any]
    """選択肢を並び替える対象属性。"""

    first_choices: list[Mapping[str, Any]]
    """先頭に移動する選択肢一覧。"""


def validate_choice_reorder_inputs(
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
    choice_ids: Sequence[str] | None,
    choice_name_ens: Sequence[str] | None,
) -> None:
    """
    選択肢並び替え入力を検証する。

    Args:
        attribute_id: 対象属性ID
        attribute_name_en: 対象属性英語名
        choice_ids: 先頭に移動する選択肢ID一覧
        choice_name_ens: 先頭に移動する選択肢英語名一覧

    Raises:
        ValueError: 入力値の組み合わせが不正な場合
    """
    if (attribute_id is None) == (attribute_name_en is None):
        raise ValueError("対象属性は `attribute_id` または `attribute_name_en` のどちらか一方だけ指定してください。")

    if (choice_ids is None) == (choice_name_ens is None):
        raise ValueError("先頭に移動する選択肢は `choice_id` または `choice_name_en` のどちらか一方だけ指定してください。")

    resolved_choice_ids = [] if choice_ids is None else list(choice_ids)
    resolved_choice_name_ens = [] if choice_name_ens is None else list(choice_name_ens)
    if len(resolved_choice_ids) == 0 and len(resolved_choice_name_ens) == 0:
        raise ValueError("先頭に移動する選択肢を1件以上指定してください。")

    duplicated_choice_ids = duplicated_set(resolved_choice_ids)
    if duplicated_choice_ids:
        duplicated_text = ", ".join(sorted(duplicated_choice_ids))
        raise ValueError(f"入力されたchoice_idに重複があります。 :: {duplicated_text}")

    duplicated_choice_name_ens = duplicated_set(resolved_choice_name_ens)
    if duplicated_choice_name_ens:
        duplicated_text = ", ".join(sorted(duplicated_choice_name_ens))
        raise ValueError(f"入力された選択肢名(英語)に重複があります。 :: {duplicated_text}")


def resolve_choice_reorder(
    annotation_specs: dict[str, Any],
    *,
    attribute_id: str | None,
    attribute_name_en: str | None,
    choice_ids: Sequence[str] | None,
    choice_name_ens: Sequence[str] | None,
) -> ResolvedChoiceReorder:
    """
    選択肢並び替え対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        attribute_id: 対象属性ID
        attribute_name_en: 対象属性英語名
        choice_ids: 先頭に移動する選択肢ID一覧
        choice_name_ens: 先頭に移動する選択肢英語名一覧

    Returns:
        解決済み選択肢並び替え対象
    """
    validate_choice_reorder_inputs(
        attribute_id=attribute_id,
        attribute_name_en=attribute_name_en,
        choice_ids=choice_ids,
        choice_name_ens=choice_name_ens,
    )
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)
    target_attribute = cast(Mapping[str, Any], annotation_specs_accessor.get_attribute(attribute_id=attribute_id, attribute_name=attribute_name_en))
    if target_attribute["type"] not in ["choice", "select"]:
        raise ValueError(f"属性ID='{target_attribute['additional_data_definition_id']}' は選択肢系属性ではありません。")

    first_choices = get_target_choices(target_attribute, choice_ids=choice_ids, choice_name_ens=choice_name_ens)
    return ResolvedChoiceReorder(target_attribute=target_attribute, first_choices=first_choices)


def create_comment_for_reorder_choices(resolved_reorder: ResolvedChoiceReorder) -> str:
    """
    選択肢並び替え時のデフォルトコメントを生成する。

    Args:
        resolved_reorder: 解決済み選択肢並び替え対象

    Returns:
        アノテーション仕様変更コメント
    """
    choice_names = [get_choice_name_en(choice) for choice in resolved_reorder.first_choices]
    return f"以下の属性の選択肢を指定順で先頭に移動しました。\n対象属性: {get_attribute_name_en(resolved_reorder.target_attribute)}\n対象選択肢: {', '.join(choice_names)}"


def create_confirm_message_for_reorder_choices(resolved_reorder: ResolvedChoiceReorder) -> str:
    """
    選択肢並び替え前の確認メッセージを生成する。

    Args:
        resolved_reorder: 解決済み選択肢並び替え対象

    Returns:
        確認メッセージ
    """
    choice_names = [get_choice_name_en(choice) for choice in resolved_reorder.first_choices]
    return (
        f"属性 '{get_attribute_name_en(resolved_reorder.target_attribute)}' の選択肢({len(resolved_reorder.first_choices)}件)を指定順で先頭に移動します。"
        f"対象選択肢={choice_names}。指定しなかった選択肢は現在の順番を維持します。よろしいですか？"
    )


def build_request_body_for_reorder_choices(
    annotation_specs: dict[str, Any],
    *,
    resolved_reorder: ResolvedChoiceReorder,
    comment: str | None,
) -> dict[str, Any]:
    """
    選択肢並び替え用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_reorder: 解決済み選択肢並び替え対象
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    target_attribute_id = resolved_reorder.target_attribute["additional_data_definition_id"]
    first_choice_ids = [choice["choice_id"] for choice in resolved_reorder.first_choices]
    first_choice_id_set = set(first_choice_ids)

    for attribute in request_body["additionals"]:
        if attribute["additional_data_definition_id"] != target_attribute_id:
            continue

        choice_dict = {choice["choice_id"]: choice for choice in attribute["choices"]}
        first_choices = [choice_dict[choice_id] for choice_id in first_choice_ids]
        remaining_choices = [choice for choice in attribute["choices"] if choice["choice_id"] not in first_choice_id_set]
        attribute["choices"] = first_choices + remaining_choices
        break

    if comment is None:
        comment = create_comment_for_reorder_choices(resolved_reorder)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class ReorderChoicesMain(CommandLineWithConfirm):
    """
    属性内の選択肢を並び替える本体処理。
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

    def reorder_choices(
        self,
        *,
        attribute_id: str | None,
        attribute_name_en: str | None,
        choice_ids: Sequence[str] | None,
        choice_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定属性内の選択肢を指定順で先頭に移動し、アノテーション仕様を更新する。

        Args:
            attribute_id: 対象属性ID
            attribute_name_en: 対象属性英語名
            choice_ids: 先頭に移動する選択肢ID一覧
            choice_name_ens: 先頭に移動する選択肢英語名一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_reorder = resolve_choice_reorder(
            old_annotation_specs,
            attribute_id=attribute_id,
            attribute_name_en=attribute_name_en,
            choice_ids=choice_ids,
            choice_name_ens=choice_name_ens,
        )

        confirm_message = create_confirm_message_for_reorder_choices(resolved_reorder)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_reorder_choices(old_annotation_specs, resolved_reorder=resolved_reorder, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"属性 '{get_attribute_name_en(resolved_reorder.target_attribute)}' の選択肢 {len(resolved_reorder.first_choices)} 件を指定順で先頭に移動しました。")
        return True


class ReorderChoices(CommandLine):
    """
    属性内の選択肢を並び替えるコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs reorder_choices: error:"

    def main(self) -> None:
        args = self.args

        choice_ids = get_list_from_args(args.choice_id) if args.choice_id is not None else None
        choice_name_ens = get_list_from_args(args.choice_name_en) if args.choice_name_en is not None else None

        obj = ReorderChoicesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.reorder_choices(
            attribute_id=args.attribute_id,
            attribute_name_en=args.attribute_name_en,
            choice_ids=choice_ids,
            choice_name_ens=choice_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``reorder_choices`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument("--attribute_name_en", type=str, help="選択肢を並び替える対象属性の英語名。")
    attribute_group.add_argument("--attribute_id", type=str, help="選択肢を並び替える対象属性のattribute_id。")

    choice_group = parser.add_mutually_exclusive_group(required=True)
    choice_group.add_argument(
        "--choice_name_en",
        type=str,
        nargs="+",
        help=(
            "先頭に移動する選択肢の英語名。複数指定した場合は、指定した順番で先頭に移動します。指定しなかった選択肢は現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"
        ),
    )
    choice_group.add_argument(
        "--choice_id",
        type=str,
        nargs="+",
        help=(
            "先頭に移動する選択肢のchoice_id。複数指定した場合は、指定した順番で先頭に移動します。"
            "指定しなかった選択肢は現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``reorder_choices`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ReorderChoices(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs reorder_choices`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "reorder_choices"
    subcommand_help = "アノテーション仕様の属性内の選択肢を並び替えます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
