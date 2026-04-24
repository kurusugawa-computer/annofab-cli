from __future__ import annotations

import argparse
import copy
import logging
import uuid
from collections.abc import Sequence

import annofabapi

import annofabcli.common.cli
from annofabcli.annotation_specs.add_label import (
    ANNOTATION_TYPE_CHOICES,
    collect_label_colors,
    create_annotation_type_help,
    create_auto_color,
    create_new_label,
    validate_new_label,
)
from annofabcli.annotation_specs.utils import get_label_name_en
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import duplicated_set

logger = logging.getLogger(__name__)


def validate_new_label_names(label_name_ens: Sequence[str]) -> None:
    """
    追加するラベル英語名一覧の入力値を検証する。

    Args:
        label_name_ens: 追加するラベル英語名一覧

    Raises:
        ValueError: 件数不足または重複がある場合
    """
    if len(label_name_ens) == 0:
        raise ValueError("追加するラベル名(英語)を1件以上指定してください。")

    duplicated_label_names: set[str] = duplicated_set(list(label_name_ens))
    if duplicated_label_names:
        duplicated_text = ", ".join(sorted(duplicated_label_names))
        raise ValueError(f"入力されたラベル名(英語)に重複があります。 :: {duplicated_text}")


def create_comment_from_labels(label_name_ens: Sequence[str]) -> str:
    """
    複数ラベル追加時のデフォルトコメントを生成する。

    Args:
        label_name_ens: 追加するラベルの英語名一覧

    Returns:
        アノテーション仕様変更コメント
    """
    label_text = ", ".join(label_name_ens)
    return f"以下のラベルを追加しました。\nラベル名(英語): {label_text}"


class AddLabelsMain(CommandLineWithConfirm):
    """
    複数ラベルをアノテーション仕様へ追加する本体処理。
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

    def add_labels(
        self,
        *,
        label_name_ens: Sequence[str],
        annotation_type: str,
        comment: str | None = None,
    ) -> bool:
        """
        複数ラベルを追加してアノテーション仕様を更新する。

        Args:
            label_name_ens: 追加するラベルの英語名一覧
            annotation_type: 追加するラベルのアノテーション種類
            comment: 変更コメント

        Returns:
            追加を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        validate_new_label_names(label_name_ens)

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        request_body = copy.deepcopy(old_annotation_specs)
        existing_label_names = {get_label_name_en(label) for label in request_body["labels"]}
        duplicated_existing_label_names = sorted(set(label_name_ens) & existing_label_names)
        if duplicated_existing_label_names:
            duplicated_text = ", ".join(duplicated_existing_label_names)
            raise ValueError(f"以下のラベル名(英語)は既に存在します。 :: {duplicated_text}")

        colors = collect_label_colors(request_body["labels"])

        confirm_message = f"{len(label_name_ens)} 件のラベルを追加します。 label_name_en={list(label_name_ens)}, annotation_type='{annotation_type}'。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        for label_name_en in label_name_ens:
            generated_label_id = str(uuid.uuid4())
            validate_new_label(request_body["labels"], label_id=generated_label_id, label_name_en=label_name_en)

            color = create_auto_color(colors)
            colors.append(color)
            new_label = create_new_label(
                label_id=generated_label_id,
                label_name_en=label_name_en,
                label_name_ja=None,
                annotation_type=annotation_type,
                color=color,
            )
            request_body["labels"].append(new_label)

        if comment is None:
            comment = create_comment_from_labels(label_name_ens)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(label_name_ens)} 件のラベルを追加しました。 :: label_name_ens={list(label_name_ens)}, annotation_type='{annotation_type}'")
        return True


class AddLabels(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_labels: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、複数ラベル追加処理を実行する。
        """
        args = self.args
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = AddLabelsMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_labels(
            label_name_ens=label_name_ens,
            annotation_type=args.annotation_type,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``add_labels`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    parser.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        required=True,
        help="追加するラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    parser.add_argument("--annotation_type", type=str, required=True, choices=ANNOTATION_TYPE_CHOICES, help=create_annotation_type_help())
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``add_labels`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddLabels(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs add_labels`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "add_labels"
    subcommand_help = "アノテーション仕様にラベルを複数追加します。"
    description = "アノテーション仕様にラベルを複数件追加します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
