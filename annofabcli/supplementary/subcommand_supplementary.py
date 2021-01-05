import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.supplementary.list_supplementary_data
import annofabcli.supplementary.delete_supplementary_data
import annofabcli.supplementary.put_supplementary_data


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.supplementary.delete_supplementary_data.add_parser(subparsers)
    annofabcli.supplementary.list_supplementary_data.add_parser(subparsers)
    annofabcli.supplementary.put_supplementary_data.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "supplementary"
    subcommand_help = "補助情報関係のサブコマンド"
    description = "補助情報関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
