import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.organization.list_organization


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.organization.list_organization.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "organization"
    subcommand_help = "組織関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, is_subcommand=False)
    parse_args(parser)
    return parser
