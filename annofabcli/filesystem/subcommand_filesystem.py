import argparse

import annofabcli.common.cli
import annofabcli.filesystem.draw_annotation
import annofabcli.filesystem.mask_user_info


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.filesystem.draw_annotation.add_parser(subparsers)
    annofabcli.filesystem.mask_user_info.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "filesystem"
    subcommand_help = "ファイル操作関係（Web APIにアクセスしない）のサブコマンド"
    description = "ファイル操作関係（Web APIにアクセスしない）のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
