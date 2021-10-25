import argparse
from typing import Optional

import annofabcli
import annofabcli.common.cli
import annofabcli.task_history_event.list_task_history_event_with_json
import annofabcli.task_history_event.list_worktime


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.task_history_event.list_task_history_event_with_json.add_parser(subparsers)
    annofabcli.task_history_event.list_worktime.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "task_history_event"
    subcommand_help = "タスク履歴イベント関係のサブコマンド"
    description = "タスク履歴イベント関係のサブコマンド。task_history_eventコマンドはベータ版です。予告なく変更される場合があります。"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
    return parser
