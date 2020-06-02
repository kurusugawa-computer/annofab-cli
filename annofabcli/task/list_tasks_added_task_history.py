import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskHistory, TaskPhase

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)

TaskHistoryDict = Dict[str, List[TaskHistory]]
"""タスク履歴の辞書（key: task_id, value: タスク履歴一覧）"""

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


class ListTasksAddedTaskHistory(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)
        self.visualize = AddProps(self.service, args.project_id)

    def _add_task_history_info(self, task: Task, task_history: Optional[TaskHistory], column_prefix: str) -> Task:
        """
        1個のタスク履歴情報を、タスクに設定する。

        Args:
            task:
            task_history:
            column_prefix:

        Returns:

        """
        if task_history is None:
            task.update(
                {
                    f"{column_prefix}_user_id": None,
                    f"{column_prefix}_username": None,
                    f"{column_prefix}_started_datetime": None,
                }
            )
            return task

        account_id = task_history["account_id"]
        task.update(
            {f"{column_prefix}_started_datetime": task_history["started_datetime"],}
        )

        organization_member = self.visualize.get_organization_member_from_account_id(account_id)
        if organization_member is not None:
            task.update(
                {
                    f"{column_prefix}_user_id": organization_member["user_id"],
                    f"{column_prefix}_username": organization_member["username"],
                }
            )
        else:
            task.update(
                {f"{column_prefix}_user_id": None, f"{column_prefix}_username": None,}
            )

        return task

    def _add_task_history_info_by_phase(
        self, task: Task, task_history_list: Optional[List[TaskHistory]], phase: TaskPhase
    ) -> Task:
        if task_history_list is not None:
            task_history_by_phase = [e for e in task_history_list if e["phase"] == phase.value]
        else:
            task_history_by_phase = []

        # 最初の対象フェーズに関する情報を設定
        first_task_history = task_history_by_phase[0] if len(task_history_by_phase) > 0 else None
        self._add_task_history_info(task, first_task_history, column_prefix=f"first_{phase.value}")

        # 最後の対象フェーズに関する情報を設定
        last_task_history = task_history_by_phase[-1] if len(task_history_by_phase) > 0 else None
        self._add_task_history_info(task, last_task_history, column_prefix=f"last_{phase.value}")

        # 作業時間に関する情報を設定
        task[f"{phase.value}_worktime_hour"] = sum(
            [
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in task_history_by_phase
            ]
        )

        return task

    def create_df_task(self, task_list: List[Dict[str, Any]], task_history_dict: TaskHistoryDict) -> pandas.DataFrame:
        for task in task_list:
            # ユーザ表示用の情報を出力する
            task = self.visualize.add_properties_to_task(task)
            task_id = task["task_id"]
            task_history_list = task_history_dict.get(task_id)
            self._add_task_history_info_by_phase(
                task=task, task_history_list=task_history_list, phase=TaskPhase.ANNOTATION
            )
            self._add_task_history_info_by_phase(
                task=task, task_history_list=task_history_list, phase=TaskPhase.INSPECTION
            )
            self._add_task_history_info_by_phase(
                task=task, task_history_list=task_history_list, phase=TaskPhase.ACCEPTANCE
            )

        return pandas.DataFrame(task_list)

    @staticmethod
    def _get_output_target_columns() -> List[str]:
        base_columns = [
            # タスクの基本情報
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "user_id",
            "username",
            "started_datetiem",
            "updated_datetiem",
            # 作業時間情報
            "worktime_hour",
            "annotation_hour",
            "inspection_hour",
            "acceptance_hour",
            # 差し戻し回数
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
        ]

        task_history_columns = [
            f"{step}_{phase.value}_{info}"
            for step in ["first", "last"]
            for phase in [TaskPhase.ANNOTATION, TaskPhase.INSPECTION, TaskPhase.ACCEPTANCE]
            for info in ["user_id", "username", "started_datetime"]
        ]
        return base_columns + task_history_columns

    def print_task_list_added_task_history(
        self, task_list: List[Dict[str, Any]], task_history_dict: TaskHistoryDict
    ) -> None:
        df_task = self.create_df_task(task_list=task_list, task_history_dict=task_history_dict)

        annofabcli.utils.print_according_to_format(
            df_task[self._get_output_target_columns()],
            arg_format=FormatArgument(FormatArgument.CSV),
            output=self.output,
            csv_format=self.csv_format,
        )

    def download_json_files(self, project_id: str, output_dir: Path, is_latest: bool, wait_options: WaitOptions):
        loop = asyncio.get_event_loop()
        downloading_obj = DownloadingFile(self.service)
        gather = asyncio.gather(
            downloading_obj.download_task_json_with_async(
                project_id, dest_path=str(output_dir / "task.json"), is_latest=is_latest, wait_options=wait_options
            ),
            downloading_obj.download_task_history_json_with_async(
                project_id, dest_path=str(output_dir / "input_data.json"),
            ),
        )
        loop.run_until_complete(gather)

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task list_merged_task_history: error:"
        if args.project_id is None and (args.task_json is None or args.task_history_json is None):
            print(
                f"{COMMON_MESSAGE} '--project_id' か、'--task_json'/'--task_history_json'ペアのいずれかを指定する必要があります。",
                file=sys.stderr,
            )
            return False

        if (args.task_json is None and args.task_history_json is not None) or (
            args.task_json is not None and args.task_history_json is None
        ):
            print(
                f"{COMMON_MESSAGE} '--task_json'と'--task_history_json'の両方を指定する必要があります。", file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            return

        project_id = args.project_id
        if project_id is not None:
            super().validate_project(project_id, [ProjectMemberRole.OWNER])
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.utils.get_cache_dir()
            self.download_json_files(project_id, cache_dir, args.latest, wait_options)
            task_json_path = cache_dir / "task.json"
            task_history_json = cache_dir / "task_history.json"
        else:
            task_json_path = args.task_json
            task_history_json = args.task_history_json

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        with open(task_history_json, encoding="utf-8") as f:
            task_history_dict = json.load(f)

        self.print_task_list_added_task_history(task_list=task_list, task_history_dict=task_history_dict)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTasksAddedTaskHistory(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "-p", "--project_id", type=str, help="対象のプロジェクトのproject_idを指定してください。" "指定すると、タスク一覧ファイル、タスク履歴一覧ファイルをダウンロードします。"
    )

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク一覧を出力します。"
        "JSONファイルは`$ annofabcli project download task`コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_history_json",
        type=str,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定してください。JSONに記載された情報を元にタスク履歴一覧を出力します。"
        "JSONファイルは`$ annofabcli project download task_history`コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="タスク一覧ファイルの更新が完了するまで待って、最新のファイルをダウンロードします（タスク履歴ファイルはWebAPIの都合上更新されません）。" "'--project_id'を指定したときのみ有効です。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスク一覧ファイル、タスク履歴一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_added_task_history"
    subcommand_help = "タスク履歴情報（作業時間、担当者）を加えたタスク一覧を出力します。"
    description = "タスク履歴情報（作業時間、担当者）を加えたタスク一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
