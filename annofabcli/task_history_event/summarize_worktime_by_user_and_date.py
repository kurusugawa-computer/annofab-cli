from __future__ import annotations

import argparse
import logging
from pathlib import Path

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_history_event.worktime import ListWorktimeFromTaskHistoryEventMain
from annofabcli.task_history_event.worktime_summary import get_df_worktime


class SummarizeWorktimeByUserAndDate(CommandLine):
    def print_worktime_list(
        self,
        project_id: str,
        task_history_event_json: Path | None,
    ) -> None:
        """タスク履歴イベントから作業時間を集計して出力する。

        Args:
            project_id: プロジェクトID。
            task_history_event_json: タスク履歴イベント全件ファイルのパス。

        Returns:
            None
        """
        super().require_project_access(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
        )
        project_member_list = self.service.wrapper.get_all_project_members(project_id, query_params={"include_inactive_member": ""})
        df = get_df_worktime(worktime_list, project_member_list)

        if self.str_format == OutputFormat.CSV.value:
            self.print_csv(df)
        else:
            self.print_according_to_format(df.to_dict(orient="records"))

    def main(self) -> None:
        """コマンドライン引数に従って集計する。

        Args:
            なし。

        Returns:
            None
        """
        args = self.args

        self.print_worktime_list(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
        )


logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    """認証して作業時間集計コマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeWorktimeByUserAndDate(service, facade, args).main()


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
    """作業時間集計のサブパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_name = "summarize_worktime_by_user_and_date"
    subcommand_help = "ユーザーごと日付ごとに作業時間を集計します。"
    description = "タスク履歴イベント全件ファイルから、ユーザーごと日付ごとに作業時間を集計します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
