from __future__ import annotations

import argparse

import annofabcli.common.cli
from annofabcli.annotation_specs.inspection_phrases import EditInspectionPhrases, add_edit_arguments
from annofabcli.common.cli import build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade


def main(args: argparse.Namespace) -> None:
    """定型指摘の追加を実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    EditInspectionPhrases(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """定型指摘追加コマンドのパーサーを作る。

    Args:
        subparsers: 親コマンドのサブパーサー。

    Returns:
        作成したパーサー。
    """
    description = (
        "アノテーション仕様の定型指摘を複数件追加します。\n\n"
        "本文には inspection_phrase_text_ja（日本語）、inspection_phrase_text_en（英語）、inspection_phrase_text_vi（ベトナム語）を指定します。"
        "未指定の言語は補完しません。IDに使用できる文字は英数字・アンダースコア・ハイフンです。"
    )
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "add_inspection_phrases",
        "アノテーション仕様の定型指摘を複数件追加します。",
        description=description,
        epilog="オーナーロールまたはチェッカーロールを持つユーザーで実行してください。",
    )
    add_edit_arguments(parser, operation="add")
    parser.set_defaults(subcommand_func=main)
    return parser
