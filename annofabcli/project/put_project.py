from __future__ import annotations

import argparse
import sys
from logging import getLogger

import annofabcli.common.cli
from annofabcli.project import create_project

logger = getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    print("[DEPRECATED] :: `project put` コマンドは非推奨です。代わりに `project create` コマンドを使用してください。`project put` コマンドは2026年01月01日以降に廃止予定です。", file=sys.stderr)  # noqa: T201
    # create_project.py の実装を使用
    create_project.main(args)


def parse_args(parser: argparse.ArgumentParser) -> None:
    # create_project.py のparse_argsと同じ実装を使用
    create_project.parse_args(parser)
    # main関数のみ差し替え
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "[DEPRECATED] プロジェクトを作成します。"
    subcommand_description = subcommand_help + "\n`project put` コマンドは非推奨です。代わりに 'project create'コマンドを使用してください。`project put` コマンドは2026年01月01日以降に廃止予定です。"

    epilog = "組織管理者、組織オーナを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_description, epilog=epilog)
    parse_args(parser)
    return parser
