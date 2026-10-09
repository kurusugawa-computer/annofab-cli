from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import annofabapi
import annofabapi.dataclass.task
from annofabapi.models import ProjectMemberRole, TaskHistory

import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
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

    def get_detail_task_list(
        self,
        task_list: list[dict[str, Any]],
        task_history_dict: TaskHistoryDict,
        start_date_list: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        obj = AddingAdditionalInfoToTask(self.service, project_id=self.project_id)

        for task in task_list:
            obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            task_histories = task_history_dict.get(task_id)
            if task_histories is None:
                logger.warning(f"task_id='{task_id}' に紐づくタスク履歴情報は存在しないので、タスク履歴の付加的情報はタスクに追加しません。")
                continue
            obj.add_task_history_additional_info_to_task(task, task_histories, start_date_list=start_date_list)

        return task_list

    def load_task_list(self, temp_dir: Path | None, *, is_latest: bool) -> list[dict[str, Any]]:
        def download_and_load(dir_path: Path) -> list[dict[str, Any]]:
            task_json_path = self.downloading_obj.download_task_json_to_dir(self.project_id, dir_path, is_latest=is_latest)
            with task_json_path.open(encoding="utf-8") as f:
                return json.load(f)

        if temp_dir is not None:
            return download_and_load(temp_dir)
        with tempfile.TemporaryDirectory() as str_temp_dir:
            return download_and_load(Path(str_temp_dir))

    def load_task_history_dict(self, temp_dir: Path | None) -> TaskHistoryDict:
        def download_and_load(dir_path: Path) -> TaskHistoryDict:
            task_history_json_path = self.downloading_obj.download_task_history_json_to_dir(self.project_id, dir_path)
            with task_history_json_path.open(encoding="utf-8") as f:
                return json.load(f)

        if temp_dir is not None:
            return download_and_load(temp_dir)
        with tempfile.TemporaryDirectory() as str_temp_dir:
            return download_and_load(Path(str_temp_dir))

    @staticmethod
    def match_task_with_conditions(
        task: dict[str, Any],
        task_id_set: set[str] | None = None,
        task_query: TaskQuery | None = None,
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
        task_id_list: list[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> list[dict[str, Any]]:
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(self.project_id, task_query)

        task_id_set = set(task_id_list) if task_id_list is not None else None
        logger.debug("出力対象のタスクを抽出しています。")
        filtered_task_list = [e for e in task_list if self.match_task_with_conditions(e, task_query=task_query, task_id_set=task_id_set)]
        return filtered_task_list

    def get_task_list_added_task_history(
        self,
        task_id_list: list[str] | None,
        task_query: TaskQuery | None,
        temp_dir: Path | None,
        *,
        is_latest_task: bool,
        start_date_list: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        タスク履歴情報を加えたタスク一覧を取得する。
        """
        task_list = self.load_task_list(temp_dir, is_latest=is_latest_task)
        task_history_dict = self.load_task_history_dict(temp_dir)

        filtered_task_list = self.filter_task_list(task_list, task_id_list=task_id_list, task_query=task_query)

        logger.debug("タスク履歴に関する付加的情報を取得しています。")
        detail_task_list = self.get_detail_task_list(task_list=filtered_task_list, task_history_dict=task_history_dict, start_date_list=start_date_list)
        return detail_task_list


class ListAllTasksAddedTaskHistory(CommandLine):
    """
    タスクの一覧を表示する
    """

    def main(self) -> None:
        args = self.args
        project_id = args.project_id

        if args.latest_task:
            logger.warning("タスク全件ファイルのみを最新化します。タスク履歴に関する列は、タスク履歴全件ファイルの時点の情報です。")

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        self.require_project_access(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        temp_dir = Path(args.temp_dir) if args.temp_dir is not None else None
        start_date_list = args.add_since_date_columns
        task_list = ListAllTasksAddedTaskHistoryMain(self.service, project_id).get_task_list_added_task_history(
            task_id_list=task_id_list,
            task_query=task_query,
            temp_dir=temp_dir,
            is_latest_task=args.latest_task,
            start_date_list=start_date_list,
        )

        logger.info(f"タスク一覧の件数: {len(task_list)}")
        TasksAddedTaskHistoryOutput(task_list, start_date_list=start_date_list).output(output_path=args.output, output_format=OutputFormat(args.format))


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
        "--latest_task",
        action="store_true",
        help="タスク全件ファイルを最新化してからダウンロードします。タスク履歴全件ファイルは更新されないため、タスク履歴に関する列は最新ではありません。"
        "タスク全件ファイルの更新には、データ数に応じて数分から数十分かかります。",
    )

    parser.add_argument(
        "--temp_dir",
        type=str,
        help="ダウンロードしたJSONファイルの保存先ディレクトリを指定できます。指定しない場合は、一時ディレクトリに保存されます。",
    )

    parser.add_argument(
        "--add_since_date_columns",
        type=str,
        nargs="+",
        metavar="YYYY-MM-DD",
        help="指定日以降の作業時間と最初の担当者情報を、追加カラムとして出力します。"
        "日付はYYYY-MM-DD形式で複数指定できます。タスク履歴のstarted_datetimeを基準に集計します。"
        "追加カラム名は ``since_{日付}.{フェーズ}_worktime_hour`` および"
        " ``since_{日付}.first_{フェーズ}_{user_id,username,started_datetime,worktime_hour}`` です。",
    )

    argument_parser.add_output()

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_all_added_task_history"
    subcommand_help = "タスク履歴に関する情報を加えたタスク一覧のすべてを出力します。"
    description = "タスク履歴に関する情報（フェーズごとの作業時間、担当者、開始日時）を加えたタスク一覧のすべてを出力します。"
    epilog = "アノテーションユーザ/オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
