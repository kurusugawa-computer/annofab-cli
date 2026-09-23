import argparse
import sys

import shtab

import annofabcli.common.cli

SHELL_CHOICES = ["bash", "fish", "powershell", "tcsh", "zsh"]
"""補完スクリプトを生成できるシェル。"""


def main(args: argparse.Namespace) -> None:
    """
    シェル補完スクリプトを標準出力に出力する。

    Args:
        args: コマンドライン引数

    Returns:
        None
    """
    sys.stdout.write(shtab.complete(args.root_parser, shell=args.shell))


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    コマンドライン引数を定義する。

    Args:
        parser: 引数を追加するパーサー

    Returns:
        None
    """
    parser.add_argument("shell", choices=SHELL_CHOICES, help="補完スクリプトを生成するシェルを指定します。")
    parser.set_defaults(subcommand_func=main, skip_logging=True)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    completionコマンドのパーサーを追加する。

    Args:
        subparsers: 親パーサーのサブパーサー

    Returns:
        追加したパーサー
    """
    command_name = "completion"
    command_help = "シェル補完スクリプトを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, command_name, command_help)
    parse_args(parser)
    return parser
