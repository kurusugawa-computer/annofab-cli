import annofabcli
import annofabcli.common.cli
import annofabcli.inspection.print_inspections
import argparse

def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.inspection.print_inspections.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "inspection"
    subcommand_help = "検査コメント関係のサブコマンド"
    description = "検査コメント関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
