import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.instruction.copy_instruction
import annofabcli.instruction.download_instruction
import annofabcli.instruction.list_instruction_history
import annofabcli.instruction.upload_instruction


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.instruction.copy_instruction.add_parser(subparsers)
    annofabcli.instruction.download_instruction.add_parser(subparsers)
    annofabcli.instruction.list_instruction_history.add_parser(subparsers)
    annofabcli.instruction.upload_instruction.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "instruction"
    subcommand_help = "作業ガイド関係のサブコマンド"
    description = "作業ガイド関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
