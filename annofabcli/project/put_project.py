from __future__ import annotations

import argparse
import sys
from typing import Optional

import annofabcli
from annofabcli.project import create_project

def main(args: argparse.Namespace) -> None:
    print(  # noqa: T201
        "⚠ 警告: `project put` コマンドは非推奨です。代わりに `project create` コマンドを使用してください。"
        "`project put` コマンドは2026年01月01日以降に廃止予定です。",
        file=sys.stderr,
    )
    # create_project.py の実装を使用
    create_project.main(args)


def parse_args(parser: argparse.ArgumentParser) -> None:
    # create_project.py のparse_argsと同じ実装を使用
    create_project.parse_args(parser)
    # main関数のみ差し替え
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "プロジェクトを作成します。"
    epilog = "組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
