import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.instruction.upload_instruction


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.instruction.upload_instruction.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "instruction"
    subcommand_help = "作業ガイド関係のサブコマンド"
    description = "作業ガイド関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
