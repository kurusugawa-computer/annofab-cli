import argparse

import annofabcli.common.cli
import annofabcli.statistics.list_annotation_count
import annofabcli.statistics.list_annotation_duration
import annofabcli.statistics.list_video_duration
import annofabcli.statistics.list_worktime
import annofabcli.statistics.summarize_task_count_by_task_id_group
import annofabcli.statistics.summarize_task_count_by_user
import annofabcli.statistics.visualize_annotation_count
import annofabcli.statistics.visualize_annotation_duration
import annofabcli.statistics.visualize_statistics
import annofabcli.statistics.visualize_video_duration


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.statistics.list_annotation_count.create_parser(subparsers)
    annofabcli.statistics.list_annotation_duration.create_parser(subparsers)

    annofabcli.statistics.list_video_duration.create_parser(subparsers)
    annofabcli.statistics.list_worktime.create_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_task_id_group.create_parser(subparsers)
    annofabcli.statistics.summarize_task_count_by_user.create_parser(subparsers)
    annofabcli.statistics.visualize_statistics.create_parser(subparsers)
    annofabcli.statistics.visualize_annotation_count.create_parser(subparsers)
    annofabcli.statistics.visualize_annotation_duration.create_parser(subparsers)
    annofabcli.statistics.visualize_video_duration.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "statistics"
    subcommand_help = "統計関係のサブコマンド"
    description = "統計関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
