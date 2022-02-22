import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.stat_visualization.merge_visualization_dir
import annofabcli.statistics.list_annotation_count
import annofabcli.statistics.list_worktime
import annofabcli.statistics.summarize_task_count
import annofabcli.statistics.summarize_task_count_by_task_id_group
import annofabcli.statistics.summarize_task_count_by_user
import annofabcli.statistics.visualize_annotation_count
import annofabcli.statistics.visualize_statistics


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.statistics.list_annotation_count.add_parser(subparsers)
    annofabcli.statistics.list_worktime.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_task_id_group.add_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_user.add_parser(subparsers)
    annofabcli.statistics.visualize_statistics.add_parser(subparsers)
    annofabcli.statistics.visualize_annotation_count.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "statistics"
    subcommand_help = "統計関係のサブコマンド"
    description = "統計関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
