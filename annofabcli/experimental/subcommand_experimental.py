import argparse

import annofabcli
import annofabcli.common.cli
from annofabcli.experimental import (
    dashboard,
    find_break_error,
    list_labor_worktime,
    list_out_of_range_annotation_for_movie,
)


def parse_args(parser: argparse.ArgumentParser):
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    dashboard.add_parser(subparsers)
    find_break_error.add_parser(subparsers)
    list_labor_worktime.add_parser(subparsers)
    list_out_of_range_annotation_for_movie.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "experimental"
    subcommand_help = "アルファ版のサブコマンド"
    description = "アルファ版のサブコマンド。予告なしに削除されたり、コマンドライン引数が変わったりします。"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
