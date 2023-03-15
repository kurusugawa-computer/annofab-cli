import argparse
from typing import Optional

import annofabcli.task_history_event.download_task_history_event_json
import annofabcli.task_history_event.list_all_task_history_event
import annofabcli.task_history_event.list_worktime
from annofabcli.common.cli import add_parser as common_add_parser


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.task_history_event.download_task_history_event_json.add_parser(subparsers)
    annofabcli.task_history_event.list_all_task_history_event.add_parser(subparsers)
    annofabcli.task_history_event.list_worktime.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "task_history_event"
    subcommand_help = "タスク履歴イベント関係のサブコマンド"
    description = "タスク履歴イベント関係のサブコマンド。task_history_eventコマンドはベータ版です。予告なく変更される場合があります。"

    parser = common_add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
