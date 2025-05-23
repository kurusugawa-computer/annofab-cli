from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
import pandas
from annofabapi.models import TaskHistoryEvent

import annofabcli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListTaskHistoryEventWithJsonMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    @staticmethod
    def filter_task_history_event(task_history_event_list: list[TaskHistoryEvent], task_id_list: Optional[list[str]] = None) -> list[TaskHistoryEvent]:
        if task_id_list is not None:
            result = []
            task_id_set = set(task_id_list)
            for event in task_history_event_list:
                if event["task_id"] in task_id_set:
                    result.append(event)  # noqa: PERF401

            return result

        return task_history_event_list

    def get_task_history_event_list(self, project_id: str, task_history_event_json: Optional[Path] = None, task_id_list: Optional[list[str]] = None) -> list[dict[str, Any]]:
        if task_history_event_json is None:
            downloading_obj = DownloadingFile(self.service)
            # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
            # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
            with tempfile.TemporaryDirectory() as str_temp_dir:
                tmp_json_file = Path(str_temp_dir) / "task_history_event.json"
                downloading_obj.download_task_history_event_json(project_id, str(tmp_json_file))
                with tmp_json_file.open(encoding="utf-8") as f:
                    all_task_history_event_list = json.load(f)

        else:
            with task_history_event_json.open(encoding="utf-8") as f:
                all_task_history_event_list = json.load(f)

        filtered_task_history_event_list = self.filter_task_history_event(all_task_history_event_list, task_id_list)

        visualize = AddProps(self.service, project_id)

        for event in filtered_task_history_event_list:
            visualize.add_properties_to_task_history_event(event)

        return filtered_task_history_event_list


class ListTaskHistoryEventWithJson(CommandLine):
    def print_task_history_event_list(
        self,
        project_id: str,
        task_history_event_json: Optional[Path],
        task_id_list: Optional[list[str]],
        arg_format: FormatArgument,
    ) -> None:
        super().validate_project(project_id, project_member_roles=None)

        main_obj = ListTaskHistoryEventWithJsonMain(self.service)
        task_history_event_list = main_obj.get_task_history_event_list(project_id, task_history_event_json=task_history_event_json, task_id_list=task_id_list)

        logger.debug(f"タスク履歴イベント一覧の件数: {len(task_history_event_list)}")

        if len(task_history_event_list) > 0:
            if arg_format == FormatArgument.CSV:
                df = pandas.json_normalize(task_history_event_list)
                self.print_csv(df)
            else:
                self.print_according_to_format(task_history_event_list)
        else:
            logger.warning("タスク履歴イベント一覧の件数が0件であるため、出力しません。")

    def main(self) -> None:
        args = self.args

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None

        self.print_task_history_event_list(
            args.project_id,
            task_history_event_json=args.task_history_event_json,
            task_id_list=task_id_list,
            arg_format=FormatArgument(args.format),
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
    ListTaskHistoryEventWithJson(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。\n``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--task_history_event_json",
        type=Path,
        help="タスク履歴イベント全件ファイルパスを指定すると、JSONに記載された情報を元にタスク履歴イベント一覧を出力します。\n"
        "JSONファイルは ``$ annofabcli task_history_event download`` コマンドで取得できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all"
    subcommand_help = "すべてのタスク履歴イベントの一覧を出力します。"
    description = "すべてのタスク履歴イベントの一覧を出力します。\n出力されるタスク履歴イベントは、コマンドを実行した日の02:00(JST)頃の状態です。最新の情報を出力する方法はありません。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
