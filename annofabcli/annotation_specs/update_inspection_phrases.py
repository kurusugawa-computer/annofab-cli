from __future__ import annotations

import argparse

import annofabcli.common.cli
from annofabcli.annotation_specs.inspection_phrases import EditInspectionPhrases, add_edit_arguments
from annofabcli.common.cli import build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade


def main(args: argparse.Namespace) -> None:
    """定型指摘の更新を実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    EditInspectionPhrases(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """定型指摘更新コマンドのパーサーを作る。

    Args:
        subparsers: 親コマンドのサブパーサー。

    Returns:
        作成したパーサー。
    """
    parser = annofabcli.common.cli.add_parser(subparsers, "update_inspection_phrases", "アノテーション仕様の定型指摘を複数件更新します。")
    add_edit_arguments(parser, operation="update")
    parser.set_defaults(subcommand_func=main)
    return parser
