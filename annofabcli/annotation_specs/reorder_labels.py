from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor, get_label_name_en

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedLabelReorder:
    """
    ラベル並び替え対象を既存アノテーション仕様に対して解決した結果。
    """

    first_labels: list[Mapping[str, Any]]
    """先頭に移動するラベル一覧。"""


def validate_label_reorder_inputs(*, label_ids: Sequence[str] | None, label_name_ens: Sequence[str] | None) -> None:
    """
    ラベル並び替え入力を検証する。

    Args:
        label_ids: 先頭に移動するラベルID一覧
        label_name_ens: 先頭に移動するラベル英語名一覧

    Raises:
        ValueError: 入力値の組み合わせが不正な場合
    """
    if (label_ids is None) == (label_name_ens is None):
        raise ValueError("先頭に移動するラベルは `label_id` または `label_name_en` のどちらか一方だけ指定してください。")

    resolved_label_ids = [] if label_ids is None else list(label_ids)
    resolved_label_name_ens = [] if label_name_ens is None else list(label_name_ens)
    if len(resolved_label_ids) == 0 and len(resolved_label_name_ens) == 0:
        raise ValueError("先頭に移動するラベルを1件以上指定してください。")

    duplicated_label_ids = duplicated_set(resolved_label_ids)
    if duplicated_label_ids:
        duplicated_text = ", ".join(sorted(duplicated_label_ids))
        raise ValueError(f"入力されたlabel_idに重複があります。 :: {duplicated_text}")

    duplicated_label_name_ens = duplicated_set(resolved_label_name_ens)
    if duplicated_label_name_ens:
        duplicated_text = ", ".join(sorted(duplicated_label_name_ens))
        raise ValueError(f"入力されたラベル名(英語)に重複があります。 :: {duplicated_text}")


def resolve_label_reorder(
    annotation_specs: dict[str, Any],
    *,
    label_ids: Sequence[str] | None,
    label_name_ens: Sequence[str] | None,
) -> ResolvedLabelReorder:
    """
    ラベル並び替え対象を既存アノテーション仕様に対して解決する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        label_ids: 先頭に移動するラベルID一覧
        label_name_ens: 先頭に移動するラベル英語名一覧

    Returns:
        解決済みラベル並び替え対象
    """
    validate_label_reorder_inputs(label_ids=label_ids, label_name_ens=label_name_ens)
    annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

    if label_ids is not None:
        first_labels = [cast(Mapping[str, Any], annotation_specs_accessor.get_label(label_id=label_id)) for label_id in label_ids]
    else:
        assert label_name_ens is not None
        first_labels = [cast(Mapping[str, Any], annotation_specs_accessor.get_label(label_name=label_name_en)) for label_name_en in label_name_ens]

    return ResolvedLabelReorder(first_labels=first_labels)


def create_comment_for_reorder_labels(resolved_reorder: ResolvedLabelReorder) -> str:
    """
    ラベル並び替え時のデフォルトコメントを生成する。

    Args:
        resolved_reorder: 解決済みラベル並び替え対象

    Returns:
        アノテーション仕様変更コメント
    """
    label_names = [get_label_name_en(label) for label in resolved_reorder.first_labels]
    return f"以下のラベルを指定順で先頭に移動しました。\n対象ラベル: {', '.join(label_names)}"


def create_confirm_message_for_reorder_labels(resolved_reorder: ResolvedLabelReorder) -> str:
    """
    ラベル並び替え前の確認メッセージを生成する。

    Args:
        resolved_reorder: 解決済みラベル並び替え対象

    Returns:
        確認メッセージ
    """
    label_names = [get_label_name_en(label) for label in resolved_reorder.first_labels]
    return f"以下のラベル({len(resolved_reorder.first_labels)}件)を指定順で先頭に移動します。対象ラベル={label_names}。指定しなかったラベルは現在の順番を維持します。よろしいですか？"


def build_request_body_for_reorder_labels(
    annotation_specs: dict[str, Any],
    *,
    resolved_reorder: ResolvedLabelReorder,
    comment: str | None,
) -> dict[str, Any]:
    """
    ラベル並び替え用の request body を生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        resolved_reorder: 解決済みラベル並び替え対象
        comment: 変更コメント

    Returns:
        Annofab API に渡す request body
    """
    request_body = copy.deepcopy(annotation_specs)
    first_label_ids = [label["label_id"] for label in resolved_reorder.first_labels]
    first_label_id_set = set(first_label_ids)
    label_dict = {label["label_id"]: label for label in request_body["labels"]}

    first_labels = [label_dict[label_id] for label_id in first_label_ids]
    remaining_labels = [label for label in request_body["labels"] if label["label_id"] not in first_label_id_set]
    request_body["labels"] = first_labels + remaining_labels

    if comment is None:
        comment = create_comment_for_reorder_labels(resolved_reorder)
    request_body["comment"] = comment
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class ReorderLabelsMain(CommandLineWithConfirm):
    """
    ラベルを並び替える本体処理。
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

    def reorder_labels(
        self,
        *,
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        comment: str | None = None,
    ) -> bool:
        """
        指定したラベルを指定順で先頭に移動し、アノテーション仕様を更新する。

        Args:
            label_ids: 先頭に移動するラベルID一覧
            label_name_ens: 先頭に移動するラベル英語名一覧
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse
        """
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        resolved_reorder = resolve_label_reorder(
            old_annotation_specs,
            label_ids=label_ids,
            label_name_ens=label_name_ens,
        )

        confirm_message = create_confirm_message_for_reorder_labels(resolved_reorder)
        if not self.confirm_processing(confirm_message):
            return False

        request_body = build_request_body_for_reorder_labels(old_annotation_specs, resolved_reorder=resolved_reorder, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(resolved_reorder.first_labels)} 件のラベルを指定順で先頭に移動しました。")
        return True


class ReorderLabels(CommandLine):
    """
    ラベルを並び替えるコマンド。
    """

    COMMON_MESSAGE = "annofabcli annotation_specs reorder_labels: error:"

    def main(self) -> None:
        args = self.args

        label_ids = get_list_from_args(args.label_id) if args.label_id is not None else None
        label_name_ens = get_list_from_args(args.label_name_en) if args.label_name_en is not None else None

        obj = ReorderLabelsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.reorder_labels(
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``reorder_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help=(
            "先頭に移動するラベルの英語名。複数指定した場合は、指定した順番で先頭に移動します。指定しなかったラベルは現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"
        ),
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help=(
            "先頭に移動するラベルのlabel_id。複数指定した場合は、指定した順番で先頭に移動します。"
            "指定しなかったラベルは現在の順番を維持します。 ``file://`` を先頭に付けると一覧ファイルを指定できます。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``reorder_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ReorderLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs reorder_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "reorder_labels"
    subcommand_help = "アノテーション仕様のラベルを並び替えます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
