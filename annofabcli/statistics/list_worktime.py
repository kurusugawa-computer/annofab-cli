import argparse
import logging

from annofabcli.common.cli import add_parser as common_add_parser
from annofabcli.task_history_event import summarize_worktime_by_user_and_date
from annofabcli.task_history_event.summarize_worktime_by_user_and_date import (
    SummarizeWorktimeByUserAndDate as ListWorktimeFromTaskHistoryEvent,
)
from annofabcli.task_history_event.summarize_worktime_by_user_and_date import (
    WorktimeDict,
    WorktimeFromTaskHistoryEvent,
    get_df_worktime,
    get_worktime_dict_from_event_list,
)

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = "[DEPRECATED] statistics list_worktimeは非推奨です。代わりに task_history_event summarize_worktime_by_user_and_dateを使用してください。"
"""旧コマンドの非推奨メッセージ。"""

__all__ = [
    "ListWorktimeFromTaskHistoryEvent",
    "WorktimeDict",
    "WorktimeFromTaskHistoryEvent",
    "get_df_worktime",
    "get_worktime_dict_from_event_list",
]


def main(args: argparse.Namespace) -> None:
    """非推奨警告を出力して移行先のコマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    logger.warning(DEPRECATED_MESSAGE)
    summarize_worktime_by_user_and_date.main(args)


def parse_args(parser: argparse.ArgumentParser) -> None:
    """旧コマンドの引数を定義する。

    Args:
        parser: 引数パーサー。

    Returns:
        None
    """
    summarize_worktime_by_user_and_date.parse_args(parser)
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """旧コマンドのサブパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_help = "[DEPRECATED] 日ごとユーザーごとの作業時間の一覧を出力します。"
    parser = common_add_parser(subparsers, "list_worktime", subcommand_help, description=f"{subcommand_help}\n{DEPRECATED_MESSAGE}")
    parse_args(parser)
    return parser
