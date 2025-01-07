from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import annofabapi
from annofabapi.models import ProjectMemberRole, TaskHistory

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query
from annofabcli.task.list_tasks_added_task_history import AddingAdditionalInfoToTask, TasksAddedTaskHistoryOutput

logger = logging.getLogger(__name__)


TaskHistoryDict = dict[str, list[TaskHistory]]
"""タスク履歴の辞書（key: task_id, value: タスク履歴一覧）"""

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


class ListAllTasksAddedTaskHistoryMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id
        self.downloading_obj = DownloadingFile(self.service)
        self.facade = AnnofabApiFacade(self.service)

    def get_detail_task_list(  # noqa: ANN201
        self,
        task_list: list[dict[str, Any]],
        task_history_dict: TaskHistoryDict,
    ):
        obj = AddingAdditionalInfoToTask(self.service, project_id=self.project_id)

        for task in task_list:
            obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            task_histories = task_history_dict.get(task_id)
            if task_histories is None:
                logger.warning(f"task_id='{task_id}' に紐づくタスク履歴情報は存在しないので、タスク履歴の付加的情報はタスクに追加しません。")
                continue
            obj.add_task_history_additional_info_to_task(task, task_histories)

        return task_list

    def load_task_list(self, task_json_path: Optional[Path]) -> list[dict[str, Any]]:
        if task_json_path is not None:
            with task_json_path.open(encoding="utf-8") as f:
                return json.load(f)

        # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
        # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
        with tempfile.TemporaryDirectory() as str_temp_dir:
            task_json_path = Path(str_temp_dir) / f"{self.project_id}__task.json"
            self.downloading_obj.download_task_json(self.project_id, str(task_json_path))
            with task_json_path.open(encoding="utf-8") as f:
                return json.load(f)

    def load_task_history_dict(self, task_history_json_path: Optional[Path]) -> TaskHistoryDict:
        if task_history_json_path is not None:
            with task_history_json_path.open(encoding="utf-8") as f:
                return json.load(f)
        else:
            # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
            # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
            with tempfile.TemporaryDirectory() as str_temp_dir:
                task_history_json_path = Path(str_temp_dir) / f"{self.project_id}__task_history.json"
                self.downloading_obj.download_task_history_json(self.project_id, str(task_history_json_path))
                with task_history_json_path.open(encoding="utf-8") as f:
                    return json.load(f)

    @staticmethod
    def match_task_with_conditions(
        task: dict[str, Any],
        task_id_set: Optional[set[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> bool:
        result = True

        dc_task = annofabapi.dataclass.task.Task.from_dict(task)
        result = result and match_task_with_query(dc_task, task_query)
        if task_id_set is not None:
            result = result and (dc_task.task_id in task_id_set)
        return result

    def filter_task_list(
        self,
        task_list: list[dict[str, Any]],
        task_id_list: Optional[list[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> list[dict[str, Any]]:
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(self.project_id, task_query)

        task_id_set = set(task_id_list) if task_id_list is not None else None
        logger.debug("出力対象のタスクを抽出しています。")
        filtered_task_list = [e for e in task_list if self.match_task_with_conditions(e, task_query=task_query, task_id_set=task_id_set)]
        return filtered_task_list

    def get_task_list_added_task_history(  # noqa: ANN201
        self,
        task_json_path: Optional[Path],
        task_history_json_path: Optional[Path],
        task_id_list: Optional[list[str]],
        task_query: Optional[TaskQuery],
    ):
        """
        タスク履歴情報を加えたタスク一覧を取得する。
        """
        task_list = self.load_task_list(task_json_path)
        task_history_dict = self.load_task_history_dict(task_history_json_path)

        filtered_task_list = self.filter_task_list(task_list, task_id_list=task_id_list, task_query=task_query)

        logger.debug("タスク履歴に関する付加的情報を取得しています。")
        detail_task_list = self.get_detail_task_list(task_list=filtered_task_list, task_history_dict=task_history_dict)
        return detail_task_list


class ListAllTasksAddedTaskHistory(CommandLine):
    """
    タスクの一覧を表示する
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task list_all_added_task_history: error:"  # noqa: N806
        if (args.task_json is None and args.task_history_json is not None) or (args.task_json is not None and args.task_history_json is None):
            print(  # noqa: T201
                f"{COMMON_MESSAGE} '--task_json'と'--task_history_json'の両方を指定する必要があります。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        self.validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        task_list = ListAllTasksAddedTaskHistoryMain(self.service, project_id).get_task_list_added_task_history(
            task_json_path=args.task_json,
            task_history_json_path=args.task_history_json,
            task_id_list=task_id_list,
            task_query=task_query,
        )

        logger.info(f"タスク一覧の件数: {len(task_list)}")
        TasksAddedTaskHistoryOutput(task_list).output(output_path=args.output, output_format=FormatArgument(args.format))


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAllTasksAddedTaskHistory(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_query()
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に出力します。指定しない場合はJSONファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task download`` コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_history_json",
        type=str,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に出力します。指定しない場合はJSONファイルをダウンロードします。\n"
        "JSONファイルは ``$ annofabcli task_history download`` コマンドで取得できます。",
    )

    argument_parser.add_output()

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all_added_task_history"
    subcommand_help = "タスク履歴に関する情報を加えたタスク一覧のすべてを出力します。"
    description = "タスク履歴に関する情報（フェーズごとの作業時間、担当者、開始日時）を加えたタスク一覧のすべてを出力します。"
    epilog = "アノテーションユーザ/オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
