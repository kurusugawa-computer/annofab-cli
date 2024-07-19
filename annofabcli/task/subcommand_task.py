import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.task.cancel_acceptance
import annofabcli.task.change_operator
import annofabcli.task.change_status_to_break
import annofabcli.task.change_status_to_on_hold
import annofabcli.task.complete_tasks
import annofabcli.task.copy_tasks
import annofabcli.task.delete_metadata_key_of_task
import annofabcli.task.delete_tasks
import annofabcli.task.download_task_json
import annofabcli.task.list_all_tasks
import annofabcli.task.list_all_tasks_added_task_history
import annofabcli.task.list_tasks
import annofabcli.task.list_tasks_added_task_history
import annofabcli.task.put_tasks
import annofabcli.task.put_tasks_by_count
import annofabcli.task.reject_tasks
import annofabcli.task.update_metadata_of_task


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.task.cancel_acceptance.add_parser(subparsers)
    annofabcli.task.change_operator.add_parser(subparsers)
    annofabcli.task.change_status_to_break.add_parser(subparsers)
    annofabcli.task.change_status_to_on_hold.add_parser(subparsers)
    annofabcli.task.complete_tasks.add_parser(subparsers)
    annofabcli.task.copy_tasks.add_parser(subparsers)
    annofabcli.task.delete_tasks.add_parser(subparsers)
    annofabcli.task.delete_metadata_key_of_task.add_parser(subparsers)
    annofabcli.task.download_task_json.add_parser(subparsers)
    annofabcli.task.list_tasks.add_parser(subparsers)
    annofabcli.task.list_tasks_added_task_history.add_parser(subparsers)
    annofabcli.task.list_all_tasks.add_parser(subparsers)
    annofabcli.task.list_all_tasks_added_task_history.add_parser(subparsers)
    annofabcli.task.put_tasks.add_parser(subparsers)
    annofabcli.task.put_tasks_by_count.add_parser(subparsers)
    annofabcli.task.reject_tasks.add_parser(subparsers)
    annofabcli.task.update_metadata_of_task.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "task"
    subcommand_help = "タスク関係のサブコマンド"
    description = "タスク関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
