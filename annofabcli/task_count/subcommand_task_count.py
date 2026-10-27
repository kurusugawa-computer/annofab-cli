import argparse

import annofabcli.common.cli
import annofabcli.task_count.list_by_metadata
import annofabcli.task_count.list_by_phase
import annofabcli.task_count.list_by_task_id_group
import annofabcli.task_count.list_by_user


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.task_count.list_by_metadata.create_parser(subparsers)
    annofabcli.task_count.list_by_phase.create_parser(subparsers)
    annofabcli.task_count.list_by_task_id_group.create_parser(subparsers)
    annofabcli.task_count.list_by_user.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "task_count"
    subcommand_help = "タスク数関係のサブコマンド"
    description = "タスク数関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
