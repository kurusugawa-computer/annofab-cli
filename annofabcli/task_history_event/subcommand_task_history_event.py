import argparse

import annofabcli.task_history_event.download_task_history_event_json
import annofabcli.task_history_event.list_all_task_history_event
import annofabcli.task_history_event.list_worktime
import annofabcli.task_history_event.summarize_worktime_by_user_and_date
from annofabcli.common.cli import create_parser as common_create_parser


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.task_history_event.download_task_history_event_json.create_parser(subparsers)
    annofabcli.task_history_event.list_all_task_history_event.create_parser(subparsers)
    annofabcli.task_history_event.list_worktime.create_parser(subparsers)
    annofabcli.task_history_event.summarize_worktime_by_user_and_date.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "task_history_event"
    subcommand_help = "タスク履歴イベント関係のサブコマンド"
    description = "タスク履歴イベント関係のサブコマンド。task_history_eventコマンドはベータ版です。予告なく変更される場合があります。"

    parser = common_create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
