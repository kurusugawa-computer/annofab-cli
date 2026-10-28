import argparse

import annofabcli.common.cli
import annofabcli.organization_member.delete_organization_member
import annofabcli.organization_member.invite_organization_member
import annofabcli.organization_member.list_organization_member
import annofabcli.organization_member.update_organization_member_role


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.organization_member.delete_organization_member.create_parser(subparsers)
    annofabcli.organization_member.invite_organization_member.create_parser(subparsers)
    annofabcli.organization_member.list_organization_member.create_parser(subparsers)
    annofabcli.organization_member.update_organization_member_role.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "organization_member"
    subcommand_help = "組織メンバ関係のサブコマンド"
    description = "組織メンバ関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
