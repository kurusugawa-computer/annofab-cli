from __future__ import annotations

import argparse
import logging
from pathlib import Path

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.worktime_summary import SummarizeWorktimeByUserAndDate as ListWorktimeFromTaskHistoryEvent

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = "[DEPRECATED] statistics list_worktimeは非推奨です。代わりに task_history_event summarize_worktime_by_user_and_dateを使用してください。"


def main(args: argparse.Namespace) -> None:
    """認証して作業時間集計コマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    logger.warning(DEPRECATED_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeFromTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """作業時間集計のコマンドライン引数を定義する。

    Args:
        parser: 引数パーサー。

    Returns:
        None
    """
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元に作業時間を集計します。\n"
        "指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task_history_event download`` コマンドで取得できます。",
    )

    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """旧コマンドのサブパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_help = "[DEPRECATED] 日ごとユーザーごとの作業時間の一覧を出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, "list_worktime", subcommand_help, description=f"{subcommand_help}\n{DEPRECATED_MESSAGE}")
    parse_args(parser)
    return parser
