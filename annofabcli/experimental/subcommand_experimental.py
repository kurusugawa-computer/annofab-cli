import argparse

import annofabcli
import annofabcli.common.cli
from annofabcli.experimental import list_labor_worktime, find_break_error


def parse_args(parser: argparse.ArgumentParser):
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    list_labor_worktime.add_parser(subparsers)  # type: ignore
    find_break_error.add_parser(subparsers)  # type: ignore


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "experimental"
    subcommand_help = "アルファ版のサブコマンド"
    description = "アルファ版のサブコマンド。予告なしに削除されたり、コマンドライン引数が変わったりします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
