import argparse

import annofabcli.stat_visualization.mask_visualization_dir
import annofabcli.stat_visualization.merge_visualization_dir
import annofabcli.stat_visualization.write_performance_rating_csv
from annofabcli.stat_visualization import (
    merge_peformance_per_date,
    merge_peformance_per_user,
    summarise_whole_peformance_csv,
    write_linegraph_per_user,
    write_performance_scatter_per_user,
    write_task_histogram,
    write_whole_linegraph,
)


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.stat_visualization.mask_visualization_dir.add_parser(subparsers)
    annofabcli.stat_visualization.merge_visualization_dir.add_parser(subparsers)
    merge_peformance_per_date.add_parser(subparsers)
    merge_peformance_per_user.add_parser(subparsers)
    summarise_whole_peformance_csv.add_parser(subparsers)
    write_linegraph_per_user.add_parser(subparsers)
    write_performance_scatter_per_user.add_parser(subparsers)
    annofabcli.stat_visualization.write_performance_rating_csv.add_parser(subparsers)
    write_task_histogram.add_parser(subparsers)
    write_whole_linegraph.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "stat_visualization"
    subcommand_help = "`annofabcli statistics visualization`コマンドの出力結果を加工するサブコマンド（アルファ版）"
    description = "`annofabcli statistics visualization`コマンドの出力結果を加工するサブコマンド（アルファ版）"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
