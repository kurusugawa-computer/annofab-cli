from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Optional

import annofabapi
import more_itertools
import pandas
from annofabapi.models import Task, TaskHistory, TaskPhase, TaskStatus
from annofabapi.util.task_history import find_rejected_task_history_indices, get_task_creation_datetime
from annofabapi.utils import get_task_history_index_skipped_acceptance, get_task_history_index_skipped_inspection

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import isoduration_to_hour, print_csv, print_json
from annofabcli.common.visualize import AddProps
from annofabcli.task.list_tasks import ListTasksMain

logger = logging.getLogger(__name__)


def get_post_rejection_annotation_worktime_hour(task_histories: list[TaskHistory]) -> float:
    """
    検査/受入フェーズでの差し戻し後の教師付作業時間を算出します。
    指摘による修正にかかった時間を把握するのに利用できます。

    Args:
        task_histories: タスク履歴

    """
    rejected_task_history_indices = find_rejected_task_history_indices(task_histories)
    if len(rejected_task_history_indices) == 0:
        return 0.0

    # 差し戻された履歴の直後で、教師付フェーズの作業時間を算出する
    min_rejected_task_history_index = min(rejected_task_history_indices)
    return sum(
        isoduration_to_hour(history["accumulated_labor_time_milliseconds"]) for history in task_histories[min_rejected_task_history_index + 1 :] if history["phase"] == TaskPhase.ANNOTATION.value
    )


def get_post_rejection_inspection_worktime_hour(task_histories: list[TaskHistory]) -> float:
    """
    検査/受入フェーズでの差し戻し後の検査作業時間を算出します。

    Args:
        task_histories: タスク履歴

    """
    rejected_task_history_indices = find_rejected_task_history_indices(task_histories)
    if len(rejected_task_history_indices) == 0:
        return 0.0

    # 差し戻された履歴の直後で、検査フェーズの作業時間を算出する
    min_rejected_task_history_index = min(rejected_task_history_indices)
    return sum(
        isoduration_to_hour(history["accumulated_labor_time_milliseconds"]) for history in task_histories[min_rejected_task_history_index + 1 :] if history["phase"] == TaskPhase.INSPECTION.value
    )


def get_post_rejection_acceptance_worktime_hour(task_histories: list[TaskHistory]) -> float:
    """
    受入フェーズでの差し戻し後の受入作業時間を算出します。


    Args:
        task_histories: タスク履歴

    """
    rejected_task_history_indices = find_rejected_task_history_indices(task_histories)

    # 検査フェーズでの差し戻しは除外する
    # 検査フェーズでの差し戻しは、受入作業の回数に影響しないため
    acceptance_rejected_indices = [index for index in rejected_task_history_indices if task_histories[index]["phase"] == TaskPhase.ACCEPTANCE.value]
    if len(acceptance_rejected_indices) == 0:
        return 0.0

    min_rejected_acceptance_task_history_index = min(acceptance_rejected_indices)

    # 差し戻された履歴の直後以降で、受入フェーズの作業時間を算出する
    return sum(
        isoduration_to_hour(history["accumulated_labor_time_milliseconds"])
        for history in task_histories[min_rejected_acceptance_task_history_index + 1 :]
        if history["phase"] == TaskPhase.ACCEPTANCE.value
    )


def get_completed_datetime(task: dict[str, Any], task_histories: list[TaskHistory]) -> Optional[str]:
    """受入完了状態になった日時を取得する。

    Args:
        task_histories (List[TaskHistory]): [description]

    Returns:
        str: 受入完了状態になった日時
    """
    # 受入完了日時を設定
    if task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value:
        assert len(task_histories) > 0, f"task_id='{task['task_id']}'のタスク履歴が0件です。参照しているタスク履歴情報が古い可能性があります。 :: phase='{task['phase']}', status='{task['status']}'"
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


def get_first_acceptance_reached_datetime(task_histories: list[TaskHistory]) -> Optional[str]:
    """
    はじめて受入フェーズに到達した日時を取得する。
    受入フェーズを着手した日時とは異なる。
    必ず`first_acceptance_started_datetime`よりも前の日時になる。

    たとえば教師付フェーズで提出して受入フェーズに到達した場合、教師付フェーズを提出した日時が「受入フェーズに到達した日時」になる。

    """
    for index, history in enumerate(task_histories):
        if history["phase"] != TaskPhase.ACCEPTANCE.value:
            continue

        first_acceptance_reached_datetime = task_histories[index - 1]["ended_datetime"]
        assert first_acceptance_reached_datetime is not None
        return first_acceptance_reached_datetime
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


def calculate_total_worktime_in_phase(task_histories: list[TaskHistory], phase: TaskPhase) -> float:
    """指定したフェーズの合計作業時間を計算する。

    Args:
        task_histories: タスク履歴
        phase: 計算対象のフェーズ

    Returns:
        合計作業時間
    """
    return sum(isoduration_to_hour(history["accumulated_labor_time_milliseconds"]) for history in task_histories if history["phase"] == phase.value)


def get_first_task_history(task_histories: list[TaskHistory], phase: TaskPhase) -> Optional[TaskHistory]:
    """
    指定したフェーズの最初に作業したタスク履歴を取得します。
    取得したタスク履歴には、account_idはnot Noneで、作業時間は0より大きいです。

    Args:
        task_histories: タスク履歴
        phase: フェーズ

    Returns:
        最初のタスク履歴
    """
    for history in task_histories:
        if history["phase"] == phase.value and history["account_id"] is not None and isoduration_to_hour(history["accumulated_labor_time_milliseconds"]) > 0:
            return history
    return None


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
    return more_itertools.first_true(task_histories[last_task_history_index + 1 :], pred=lambda e: e["phase"] == TaskPhase.INSPECTION.value) is None


class AddingAdditionalInfoToTask:
    """タスクに付加的な情報を追加するためのクラス

    Args:
        service: annofabapiにアクセスするためのインスタンス
        project_id: プロジェクトID

    """

    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
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
                    f"{column_prefix}_worktime_hour": 0,  # 作業時間はNoneでなく0を設定する。
                }
            )
            return task

        account_id = task_history["account_id"]
        task.update(
            {
                f"{column_prefix}_started_datetime": task_history["started_datetime"],
                f"{column_prefix}_worktime_hour": annofabcli.common.utils.isoduration_to_hour(task_history["accumulated_labor_time_milliseconds"]),
            }
        )

        member = self.visualize.get_project_member_from_account_id(account_id)
        if member is not None:
            task.update(
                {
                    f"{column_prefix}_user_id": member["user_id"],
                    f"{column_prefix}_username": member["username"],
                }
            )
        else:
            task.update({f"{column_prefix}_user_id": None, f"{column_prefix}_username": None})

        return task

    def add_additional_info_to_task(self, task: dict[str, Any]) -> None:
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

    def add_task_history_additional_info_to_task(self, task: dict[str, Any], task_histories: list[TaskHistory]) -> None:
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
        # タスク作成日時
        task["created_datetime"] = get_task_creation_datetime(task, task_histories)

        # フェーズごとのタスク履歴情報を追加する
        for phase in TaskPhase:
            # タスク履歴から取得した作業時間を設定
            task[f"{phase.value}_worktime_hour"] = calculate_total_worktime_in_phase(task_histories, phase)
            first_task_history = get_first_task_history(task_histories, phase)
            self._add_task_history_info(task, first_task_history, column_prefix=f"first_{phase.value}")

        # 初めて受入が完了した日時
        task["first_acceptance_reached_datetime"] = get_first_acceptance_reached_datetime(task_histories)
        task["first_acceptance_completed_datetime"] = get_first_acceptance_completed_datetime(task_histories)

        # 受入完了日時を設定
        task["completed_datetime"] = get_completed_datetime(task, task_histories)

        # 抜取検査/受入によって、スキップされたかどうか
        task["inspection_is_skipped"] = is_inspection_phase_skipped(task_histories)
        task["acceptance_is_skipped"] = is_acceptance_phase_skipped(task_histories)

        task["post_rejection_annotation_worktime_hour"] = get_post_rejection_annotation_worktime_hour(task_histories)
        task["post_rejection_inspection_worktime_hour"] = get_post_rejection_inspection_worktime_hour(task_histories)
        task["post_rejection_acceptance_worktime_hour"] = get_post_rejection_acceptance_worktime_hour(task_histories)


class ListTasksAddedTaskHistoryMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

    def main(self, *, task_query: Optional[dict[str, Any]], task_id_list: Optional[list[str]]) -> list[dict[str, Any]]:
        list_task_obj = ListTasksMain(self.service, self.project_id)
        task_list = list_task_obj.get_task_list(self.project_id, task_id_list=task_id_list, task_query=task_query)

        obj = AddingAdditionalInfoToTask(self.service, project_id=self.project_id)
        logger.info(f"{len(task_list)} 件のタスクの履歴情報を取得します。")

        for index, task in enumerate(task_list):
            if (index + 1) % 100 == 0:
                logger.debug(f"{index + 1} 件目のタスク履歴情報を取得します。")

            obj.add_additional_info_to_task(task)
            task_id = task["task_id"]

            try:
                task_histories, _ = self.service.api.get_task_histories(self.project_id, task_id)
                # タスク履歴から取得した情報をtaskに設定する
                obj.add_task_history_additional_info_to_task(task, task_histories)
            except Exception:
                logger.warning(f"task_id='{task_id}' :: タスク履歴に関する情報を取得するのに失敗しました。", exc_info=True)

        return task_list


class TasksAddedTaskHistoryOutput:
    """出力用のクラス"""

    def __init__(self, task_list: list[dict[str, Any]]) -> None:
        self.task_list = task_list

    @staticmethod
    def _get_output_target_columns() -> list[str]:
        base_columns = [
            # タスクの基本情報
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "created_datetime",
            "started_datetime",
            "updated_datetime",
            "operation_updated_datetime",
            "account_id",
            "user_id",
            "username",
            "input_data_count",
            "metadata",
            "sampling",
            # 作業時間情報
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 差し戻し回数
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            "first_acceptance_reached_datetime",
            "first_acceptance_completed_datetime",
            "completed_datetime",
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

        task_history_columns = [
            f"first_{phase.value}_{info}" for phase in [TaskPhase.ANNOTATION, TaskPhase.INSPECTION, TaskPhase.ACCEPTANCE] for info in ["user_id", "username", "started_datetime", "worktime_hour"]
        ]

        return (
            base_columns
            + task_history_columns
            + [
                "post_rejection_annotation_worktime_hour",
                "post_rejection_inspection_worktime_hour",
                "post_rejection_acceptance_worktime_hour",
            ]
        )

    def output(self, output_path: Path, output_format: FormatArgument) -> None:
        task_list = self.task_list
        if len(task_list) == 0:
            logger.info("タスク一覧の件数が0件のため、出力しません。")
            return

        logger.debug(f"タスク一覧の件数: {len(task_list)}")
        if output_format == FormatArgument.CSV:
            df_task = pandas.DataFrame(task_list)
            print_csv(
                df_task[self._get_output_target_columns()],
                output=output_path,
            )
        elif output_format == FormatArgument.JSON:
            print_json(task_list, is_pretty=False, output=output_path)
        elif output_format == FormatArgument.PRETTY_JSON:
            print_json(task_list, is_pretty=True, output=output_path)


class ListTasksAddedTaskHistory(CommandLine):
    def main(self) -> None:
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = annofabcli.common.cli.get_json_from_args(args.task_query) if args.task_query is not None else None

        main_obj = ListTasksAddedTaskHistoryMain(self.service, project_id=args.project_id)
        task_list = main_obj.main(task_query=task_query, task_id_list=task_id_list)

        output_obj = TasksAddedTaskHistoryOutput(task_list)
        output_obj.output(args.output, output_format=FormatArgument(args.format))


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTasksAddedTaskHistory(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    query_group = parser.add_mutually_exclusive_group()

    # タスク検索クエリ
    query_group.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合は、すべてのタスクを取得します。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのフォーマットは、`getTasks <https://annofab.com/docs/api/#operation/getTasks>`_ APIのクエリパラメータと同じです。"
        "さらに追加で、``user_id`` , ``previous_user_id`` キーも指定できます。"
        "ただし ``page`` , ``limit`` キーは指定できません。",
    )

    query_group.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="対象のタスクのtask_idを指定します。 ``--task_query`` 引数とは同時に指定できません。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    argument_parser.add_output()

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "list_added_task_history"
    subcommand_help = "タスク履歴に関する情報を加えたタスク一覧を出力します。"
    description = "タスク履歴に関する情報（フェーズごとの作業時間、担当者、開始日時）を加えたタスク一覧を出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
