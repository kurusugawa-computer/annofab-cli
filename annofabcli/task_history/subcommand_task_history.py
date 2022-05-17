import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.task_history.download_task_history_json
import annofabcli.task_history.list_task_history
import annofabcli.task_history.list_task_history_with_json


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.task_history.download_task_history_json.add_parser(subparsers)
    annofabcli.task_history.list_task_history.add_parser(subparsers)
    annofabcli.task_history.list_task_history_with_json.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "task_history"
    subcommand_help = "タスク履歴関係のサブコマンド"
    description = "タスク履歴関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
