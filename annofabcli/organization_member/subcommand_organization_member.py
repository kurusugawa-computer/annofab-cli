import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.organization_member.change_organization_member
import annofabcli.organization_member.delete_organization_member
import annofabcli.organization_member.invite_organization_member
import annofabcli.organization_member.list_organization_member


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.organization_member.change_organization_member.add_parser(subparsers)
    annofabcli.organization_member.delete_organization_member.add_parser(subparsers)
    annofabcli.organization_member.invite_organization_member.add_parser(subparsers)
    annofabcli.organization_member.list_organization_member.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "organization_member"
    subcommand_help = "組織メンバ関係のサブコマンド"
    description = "組織メンバ関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
