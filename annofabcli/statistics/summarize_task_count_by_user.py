import argparse
import logging

import annofabcli.common.cli
import annofabcli.task_count.list_by_user
from annofabcli.task_count.list_by_user import (
    DEFAULT_TASK_ID_DELIMITER,
    DEFAULT_WAIT_OPTIONS,
    ListTaskCountByUser,
    TaskStatusForSummary,
    add_info_to_task,
    create_task_count_summary_df,
)

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `statistics summarize_task_count_by_user` コマンドは非推奨です。"
    "代わりに `task_count list_by_user` コマンドを使用してください。 "
    "`statistics summarize_task_count_by_user` コマンドは2027/01/01以降に廃止予定です。"
)

# Pythonコードから参照している利用者に対する互換性を維持する。
SummarizeTaskCountByUser = ListTaskCountByUser

__all__ = [
    "DEFAULT_TASK_ID_DELIMITER",
    "DEFAULT_WAIT_OPTIONS",
    "SummarizeTaskCountByUser",
    "TaskStatusForSummary",
    "add_info_to_task",
    "create_task_count_summary_df",
]


def parse_args(parser: argparse.ArgumentParser) -> None:
    """旧コマンドのコマンドライン引数を定義する。

    Args:
        parser: 引数パーサー。

    Returns:
        None
    """
    annofabcli.task_count.list_by_user.parse_args(parser, include_metadata_key=False)
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """非推奨警告を出力して、移行先と同じ処理を実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    logger.warning(DEPRECATED_MESSAGE)
    annofabcli.task_count.list_by_user.main(args)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """旧コマンドのサブパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_name = "summarize_task_count_by_user"
    subcommand_help = f"ユーザごとに、担当しているタスク数を出力します。\n{DEPRECATED_MESSAGE}"
    description = f"ユーザごとに、担当しているタスク数をCSV形式で出力します。\n{DEPRECATED_MESSAGE}"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
