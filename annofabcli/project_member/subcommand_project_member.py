import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.project_member.change_project_members
import annofabcli.project_member.copy_project_members
import annofabcli.project_member.drop_project_members
import annofabcli.project_member.invite_project_members
import annofabcli.project_member.list_users
import annofabcli.project_member.put_project_members


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.project_member.change_project_members.add_parser(subparsers)
    annofabcli.project_member.copy_project_members.add_parser(subparsers)
    annofabcli.project_member.drop_project_members.add_parser(subparsers)
    annofabcli.project_member.invite_project_members.add_parser(subparsers)
    annofabcli.project_member.list_users.add_parser(subparsers)
    annofabcli.project_member.put_project_members.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "project_member"
    subcommand_help = "プロジェクトメンバ関係のサブコマンド"
    description = "プロジェクトメンバ関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
