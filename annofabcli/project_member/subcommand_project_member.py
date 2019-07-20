import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.project_member.delete_users
import annofabcli.project_member.invite_users
import annofabcli.project_member.list_users


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.project_member.list_users.add_parser(subparsers)
    annofabcli.project_member.invite_users.add_parser(subparsers)
    annofabcli.project_member.delete_users.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "project_member"
    subcommand_help = "プロジェクトメンバ関係のサブコマンド"
    description = "プロジェクトメンバ関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
