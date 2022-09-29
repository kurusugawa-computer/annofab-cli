import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.my_account.get_my_account


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.my_account.get_my_account.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "my_account"
    subcommand_help = "自分のアカウント関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, is_subcommand=False)
    parse_args(parser)
    return parser
