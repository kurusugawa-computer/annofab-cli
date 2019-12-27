import argparse

import annofabcli
import annofabcli.annotation.list_annotation_count
import annofabcli.common.cli


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.annotation.list_annotation_count.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "annotation"
    subcommand_help = "アノテーション関係のサブコマンド"
    description = "アノテーション関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
