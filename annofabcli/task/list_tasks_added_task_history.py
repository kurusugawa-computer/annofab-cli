from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import annofabapi
import more_itertools
import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskHistory, TaskPhase, TaskStatus
from annofabapi.utils import get_task_history_index_skipped_acceptance, get_task_history_index_skipped_inspection

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_wait_options_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_task_with_query
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)

TaskHistoryDict = Dict[str, List[TaskHistory]]
"""タスク履歴の辞書（key: task_id, value: タスク履歴一覧）"""

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def get_completed_datetime(task: dict[str, Any], task_histories: list[TaskHistory]) -> Optional[str]:
    """受入完了状態になった日時を取得する。

    Args:
        task_histories (List[TaskHistory]): [description]

    Returns:
        str: 受入完了状態になった日時
    """
    # 受入完了日時を設定
    if task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value:
        assert len(task_histories) > 0
        return task_histories[-1]["ended_datetime"]
    else:
        return None


def get_first_acceptance_completed_datetime(task_histories: list[TaskHistory]) -> Optional[str]:
    """はじめて受入完了状態になった日時を取得する。

    Args:
        task_histories (List[TaskHistory]): [description]

    Returns:
        str: はじめて受入完了状態になった日時
    """
    # 受入フェーズで完了日時がnot Noneの場合は、受入を合格したか差し戻したとき。
    # したがって、後続のタスク履歴を見て、初めて受入完了状態になった日時を取得する。

    for index, history in enumerate(task_histories):
        if history["phase"] != TaskPhase.ACCEPTANCE.value or history["ended_datetime"] is None:
            continue

        if index == len(task_histories) - 1:
            # 末尾履歴なら、受入完了状態
            return history["ended_datetime"]

        next_history = task_histories[index + 1]
        if next_history["phase"] == TaskPhase.ACCEPTANCE.value:
            # 受入完了後、受入取り消し実行
            return history["ended_datetime"]
        # そうでなければ、受入フェーズでの差し戻し

    return None


def is_acceptance_phase_skipped(task_histories: list[TaskHistory]) -> bool:
    """抜取受入によって、受入フェーズでスキップされたことがあるかを取得する。

    Args:
        task_histories (List[TaskHistory]): タスク履歴

    Returns:
        bool: 受入フェーズでスキップされたことがあるかどうか
    """
    task_history_index_list = get_task_history_index_skipped_acceptance(task_histories)
    if len(task_history_index_list) == 0:
        return False

    # スキップされた履歴より後に受入フェーズがなければ、受入がスキップされたタスクとみなす
    # ただし、スキップされた履歴より後で、「アノテーション一覧で修正された」受入フェーズがある場合（account_id is None）は、スキップされた受入とみなす。
    last_task_history_index = task_history_index_list[-1]
    return (
        more_itertools.first_true(
            task_histories[last_task_history_index + 1 :],
            pred=lambda e: e["phase"] == TaskPhase.ACCEPTANCE.value and e["account_id"] is not None,
        )
        is None
    )


def is_inspection_phase_skipped(task_histories: list[TaskHistory]) -> bool:
    """抜取検査によって、検査フェーズでスキップされたことがあるかを取得する。

    Args:
        task_histories (List[TaskHistory]): タスク履歴

    Returns:
        bool: 検査フェーズでスキップされたことがあるかどうか
    """
    task_history_index_list = get_task_history_index_skipped_inspection(task_histories)
    if len(task_history_index_list) == 0:
        return False

    # スキップされた履歴より後に検査フェーズがなければ、検査がスキップされたタスクとみなす
    last_task_history_index = task_history_index_list[-1]
    return (
        more_itertools.first_true(
            task_histories[last_task_history_index + 1 :], pred=lambda e: e["phase"] == TaskPhase.INSPECTION.value
        )
        is None
    )


class AddingAdditionalInfoToTask:
    """タスクに付加的な情報を追加するためのクラス

    Args:
        service: annofabapiにアクセスするためのインスタンス
        project_id: プロジェクトID

    """

    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.project_id = project_id
        self.visualize = AddProps(self.service, project_id)

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
                    f"{column_prefix}_worktime_hour": None,
                }
            )
            return task

        account_id = task_history["account_id"]
        task.update(
            {
                f"{column_prefix}_started_datetime": task_history["started_datetime"],
                f"{column_prefix}_worktime_hour": annofabcli.common.utils.isoduration_to_hour(
                    task_history["accumulated_labor_time_milliseconds"]
                ),
            }
        )

        organization_member = self.visualize.get_project_member_from_account_id(account_id)
        if organization_member is not None:
            task.update(
                {
                    f"{column_prefix}_user_id": organization_member["user_id"],
                    f"{column_prefix}_username": organization_member["username"],
                }
            )
        else:
            task.update({f"{column_prefix}_user_id": None, f"{column_prefix}_username": None})

        return task

    def _add_task_history_info_by_phase(
        self, task: dict[str, Any], task_histories: list[TaskHistory], phase: TaskPhase
    ) -> Task:
        if task_histories is not None:
            task_history_by_phase = [
                e
                for e in task_histories
                if e["phase"] == phase.value
                and e["account_id"] is not None
                and annofabcli.common.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
            ]
        else:
            task_history_by_phase = []

        # 最初の対象フェーズに関する情報を設定
        first_task_history = task_history_by_phase[0] if len(task_history_by_phase) > 0 else None
        self._add_task_history_info(task, first_task_history, column_prefix=f"first_{phase.value}")

        # 作業時間に関する情報を設定
        task[f"{phase.value}_worktime_hour"] = sum(
            annofabcli.common.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
            for e in task_history_by_phase
        )

        return task

    def add_additional_info_to_task(self, task: dict[str, Any]):
        """タスクの付加的情報を、タスクに追加する。
        以下の列を追加する。
        * user_id
        * username
        * number_of_rejections_by_inspection
        * number_of_rejections_by_acceptance
        * worktime_hour


        Args:
            task (dict[str,Any]): (IN/OUT) タスク情報

        """
        # タスク情報から取得できる、付加的な情報を追加する
        self.visualize.add_properties_to_task(task)

    def add_task_history_additional_info_to_task(self, task: dict[str, Any], task_histories: list[TaskHistory]):
        """タスク履歴から取得できる付加的情報を、タスクに追加する。
        以下の列を追加する。
        * annotation_worktime_hour
        * first_annotation_user_id
        * first_annotation_username
        * first_annotation_started_datetime
        ... inspection, acceptanceも同様

        * first_acceptance_completed_datetime
        * completed_datetime
        * inspection_is_skipped
        * acceptance_is_skipped

        Args:
            task (dict[str,Any]): (IN/OUT) タスク情報
            task_histories (list[TaskHistory]): タスク履歴

        """
        # タスク情報から取得できる、付加的な情報を追加する
        task = self.visualize.add_properties_to_task(task)

        # フェーズごとのタスク履歴情報を追加する
        self._add_task_history_info_by_phase(task, task_histories, phase=TaskPhase.ANNOTATION)
        self._add_task_history_info_by_phase(task, task_histories, phase=TaskPhase.INSPECTION)
        self._add_task_history_info_by_phase(task, task_histories, phase=TaskPhase.ACCEPTANCE)

        # 初めて受入が完了した日時
        task["first_acceptance_completed_datetime"] = get_first_acceptance_completed_datetime(task_histories)

        # 受入完了日時を設定
        task["completed_datetime"] = get_completed_datetime(task, task_histories)

        # 抜取検査/受入によって、スキップされたかどうか
        task["inspection_is_skipped"] = is_inspection_phase_skipped(task_histories)
        task["acceptance_is_skipped"] = is_acceptance_phase_skipped(task_histories)


class ListTasksAddedTaskHistory(AbstractCommandLineInterface):
    """
    タスクの一覧を表示する
    """

    def get_detail_task_list(
        self,
        task_list: List[Dict[str, Any]],
        task_history_dict: TaskHistoryDict,
        project_id: str,
    ):
        obj = AddingAdditionalInfoToTask(self.service, project_id=project_id)

        for task in task_list:

            obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            task_histories = task_history_dict.get(task_id)
            if task_histories is None:
                logger.warning(f"task_id='{task_id}' に紐づくタスク履歴情報は存在しないので、タスク履歴の付加的情報はタスクに追加しません。")
                continue
            obj.add_task_history_additional_info_to_task(task, task_histories)

        return task_list

    @staticmethod
    def _get_output_target_columns() -> List[str]:
        base_columns = [
            # タスクの基本情報
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "started_datetime",
            "updated_datetime",
            "user_id",
            "username",
            # 作業時間情報
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 差し戻し回数
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            "first_acceptance_completed_datetime",
            "completed_datetime",
            "inspection_is_skipped",
            "acceptance_is_skipped",
            "sampling",
        ]

        task_history_columns = [
            f"first_{phase.value}_{info}"
            for phase in [TaskPhase.ANNOTATION, TaskPhase.INSPECTION, TaskPhase.ACCEPTANCE]
            for info in ["user_id", "username", "started_datetime", "worktime_hour"]
        ]

        return base_columns + task_history_columns

    def download_json_files(
        self,
        project_id: str,
        task_json_path: Path,
        task_history_json_path: Path,
        is_latest: bool,
        wait_options: WaitOptions,
    ):
        loop = asyncio.get_event_loop()
        downloading_obj = DownloadingFile(self.service)
        gather = asyncio.gather(
            downloading_obj.download_task_json_with_async(
                project_id, dest_path=str(task_json_path), is_latest=is_latest, wait_options=wait_options
            ),
            downloading_obj.download_task_history_json_with_async(
                project_id,
                dest_path=str(task_history_json_path),
            ),
        )
        loop.run_until_complete(gather)

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli task list_merged_task_history: error:"
        if (args.task_json is None and args.task_history_json is not None) or (
            args.task_json is not None and args.task_history_json is None
        ):
            print(
                f"{COMMON_MESSAGE} '--task_json'と'--task_history_json'の両方を指定する必要があります。",
                file=sys.stderr,
            )
            return False

        return True

    @staticmethod
    def match_task_with_conditions(
        task: Dict[str, Any],
        task_id_set: Optional[Set[str]] = None,
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
        project_id: str,
        task_list: List[Dict[str, Any]],
        task_id_list: Optional[List[str]] = None,
        task_query: Optional[TaskQuery] = None,
    ) -> List[Dict[str, Any]]:
        if task_query is not None:
            task_query = self.facade.set_account_id_of_task_query(project_id, task_query)

        task_id_set = set(task_id_list) if task_id_list is not None else None
        logger.debug(f"出力対象のタスクを抽出しています。")
        filtered_task_list = [
            e for e in task_list if self.match_task_with_conditions(e, task_query=task_query, task_id_set=task_id_set)
        ]
        return filtered_task_list

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id = args.project_id

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if args.task_json is not None and args.task_history_json is not None:
            task_json_path = args.task_json
            task_history_json_path = args.task_history_json
        else:
            wait_options = get_wait_options_from_args(get_json_from_args(args.wait_options), DEFAULT_WAIT_OPTIONS)
            cache_dir = annofabcli.common.utils.get_cache_dir()
            task_json_path = cache_dir / f"{project_id}-task.json"
            task_history_json_path = cache_dir / f"{project_id}-task_history.json"
            self.download_json_files(
                project_id,
                task_json_path=task_json_path,
                task_history_json_path=task_history_json_path,
                is_latest=args.latest,
                wait_options=wait_options,
            )

        with open(task_json_path, encoding="utf-8") as f:
            task_list = json.load(f)

        with open(task_history_json_path, encoding="utf-8") as f:
            task_history_dict = json.load(f)

        filtered_task_list = self.filter_task_list(
            project_id, task_list, task_id_list=task_id_list, task_query=task_query
        )

        logger.debug(f"タスク履歴に関する付加的情報を取得しています。")
        detail_task_list = self.get_detail_task_list(
            project_id=project_id, task_list=filtered_task_list, task_history_dict=task_history_dict
        )

        df_task = pandas.DataFrame(detail_task_list)

        annofabcli.common.utils.print_according_to_format(
            df_task[self._get_output_target_columns()],
            arg_format=FormatArgument(FormatArgument.CSV),
            output=self.output,
            csv_format=self.csv_format,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTasksAddedTaskHistory(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_query()
    argument_parser.add_task_id(required=False)

    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に出力します。指定しない場合はJSONファイルをダウンロードします。"
        "JSONファイルは`$ annofabcli project download task`コマンドで取得できます。",
    )

    parser.add_argument(
        "--task_history_json",
        type=str,
        help="タスク履歴情報が記載されたJSONファイルのパスを指定すると、JSONに記載された情報を元に出力します。指定しない場合はJSONファイルをダウンロードします。"
        "JSONファイルは`$ annofabcli project download task_history`コマンドで取得できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="タスク一覧ファイルの更新が完了するまで待って、最新のファイルをダウンロードします（タスク履歴ファイルはWebAPIの都合上更新されません）。" "JSONファイルを指定しなかったときに有効です。",
    )

    parser.add_argument(
        "--wait_options",
        type=str,
        help="タスク一覧ファイルの更新が完了するまで待つ際のオプションを、JSON形式で指定してください。"
        "`file://`を先頭に付けるとjsonファイルを指定できます。"
        'デフォルは`{"interval":60, "max_tries":360}` です。'
        "`interval`:完了したかを問い合わせる間隔[秒], "
        "`max_tires`:完了したかの問い合わせを最大何回行うか。",
    )

    argument_parser.add_output()
    argument_parser.add_csv_format()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list_added_task_history"
    subcommand_help = "タスク履歴情報を加えたタスク一覧を出力します。"
    description = "タスク履歴情報（フェーズごとの作業時間、担当者、開始日時）を加えたタスク一覧をCSV形式で出力します。"
    epilog = "アノテーションユーザ/オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
