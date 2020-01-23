import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.labor.list_worktime_by_user


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.labor.list_worktime_by_user.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "labor"
    subcommand_help = "労務管理関係のサブコマンド"
    description = "労務管理関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
