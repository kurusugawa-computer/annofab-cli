import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.stat_visualization.merge_visualization_dir
import annofabcli.statistics.list_annotation_count
import annofabcli.statistics.list_by_date_user
import annofabcli.statistics.list_cumulative_labor_time
import annofabcli.statistics.list_labor_time_per_user
import annofabcli.statistics.list_task_progress
import annofabcli.statistics.summarize_task_count
import annofabcli.statistics.summarize_task_count_by_task_id
import annofabcli.statistics.summarize_task_count_by_user
import annofabcli.statistics.visualize_statistics


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.statistics.list_annotation_count.add_parser(subparsers)
    annofabcli.statistics.list_by_date_user.add_parser(subparsers)
    annofabcli.statistics.list_cumulative_labor_time.add_parser(subparsers)
    annofabcli.statistics.list_labor_time_per_user.add_parser(subparsers)
    annofabcli.statistics.list_task_progress.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_task_id.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_user.add_parser(subparsers)
    annofabcli.statistics.visualize_statistics.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "statistics"
    subcommand_help = "統計関係のサブコマンド"
    description = "統計関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
