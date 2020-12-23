import argparse

import annofabcli.stat_visualization.write_performance_rating_csv


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.stat_visualization.write_performance_rating_csv.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "stat_visualization"
    subcommand_help = "`annofabcli statistics visualization`コマンドの出力結果を加工するサブコマンド"
    description = "`annofabcli statistics visualization`コマンドの出力結果を加工するサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
