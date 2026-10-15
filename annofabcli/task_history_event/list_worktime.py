from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas

import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.task_history_worktime import (
    ListWorktimeFromTaskHistoryEventMain,
)

logger = logging.getLogger(__name__)


class ListWorktimeFromTaskHistoryEvent(CommandLine):
    def print_worktime_from_task_history_event(
        self,
        project_id: str,
        task_history_event_json: Path | None,
        task_id_list: list[str] | None,
        user_id_list: list[str] | None,
        arg_format: OutputFormat,
        temp_dir: Path | None = None,
    ) -> None:
        super().require_project_access(project_id, project_member_roles=None)

        main_obj = ListWorktimeFromTaskHistoryEventMain(self.service, project_id=project_id)
        worktime_list = main_obj.get_worktime_list(
            project_id,
            task_history_event_json=task_history_event_json,
            task_id_list=task_id_list,
            user_id_list=user_id_list,
            temp_dir=temp_dir,
        )

        logger.debug(f"作業時間一覧の件数: {len(worktime_list)}")
        dict_worktime_list = [e.to_dict() for e in worktime_list]

        if arg_format == OutputFormat.CSV:
            columns = [
                "project_id",
                "task_id",
                "phase",
                "phase_stage",
                "account_id",
                "user_id",
                "username",
                "worktime_hour",
                "start_event.task_history_id",
                "start_event.created_datetime",
                "start_event.status",
                "end_event.task_history_id",
                "end_event.created_datetime",
                "end_event.status",
                "end_event_request.status",
                "end_event_request.force",
                "end_event_request.account_id",
                "end_event_request.user_id",
                "end_event_request.username",
            ]

            if len(dict_worktime_list) > 0:
                df = pandas.json_normalize(dict_worktime_list)[columns]
            else:
                df = pandas.DataFrame(columns=columns)
            self.print_csv(df)
        else:
            self.print_according_to_format(dict_worktime_list)

    def main(self) -> None:
        args = self.args

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

        self.print_worktime_from_task_history_event(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
            task_id_list=task_id_list,
            user_id_list=user_id_list,
            arg_format=OutputFormat(args.format),
            temp_dir=args.temp_dir,
        )

    @staticmethod
    def to_all_task_history_event_list_from_dict(task_history_event_dict: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        all_task_history_event_list = []
        for task_history_event_list in task_history_event_dict.values():
            all_task_history_event_list.extend(task_history_event_list)
        return all_task_history_event_list


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeFromTaskHistoryEvent(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help=(
            "対象のタスクのtask_idを指定します。"
            "\n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help=(
            "絞り込み対象のユーザのuser_idを指定します。"
            "\n``file://`` を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元にタスク履歴イベント一覧を出力します。\n"
        "指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task_history_event download`` コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、タスク履歴イベントJSONなどの一時ファイルをダウンロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_worktime"
    subcommand_help = "タスク履歴イベントから作業時間の一覧を出力します。"
    description = "タスク履歴イベントから作業時間の一覧を出力します。\nタスク履歴より詳細な作業時間の情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
