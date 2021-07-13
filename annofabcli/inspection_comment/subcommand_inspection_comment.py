import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.inspection_comment.list_inspections
import annofabcli.inspection_comment.list_inspections_with_json


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.inspection_comment.list_inspections.add_parser(subparsers)
    annofabcli.inspection_comment.list_inspections_with_json.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "inspection_comment"
    subcommand_help = "検査コメント関係のサブコマンド"
    description = "検査コメント関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
