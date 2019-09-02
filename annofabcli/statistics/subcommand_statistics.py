import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.statistics.visualize


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest='subcommand_name')

    # サブコマンドの定義
    annofabcli.statistics.visualize(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "statistics"
    subcommand_help = "統計関係のサブコマンド"
    description = "統計関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
