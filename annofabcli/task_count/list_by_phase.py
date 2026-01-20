import argparse
import json
import logging
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

import isodate
import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskPhase, TaskStatus
from annofabapi.resource import Resource as AnnofabResource
from annofabapi.utils import get_number_of_rejections

import annofabcli.common
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.type_util import assert_noreturn

logger = logging.getLogger(__name__)


class AggregationUnit(Enum):
    """
    集計の単位。
    """

    TASK = "task"
    """タスク数"""
    INPUT_DATA = "input_data"
    """入力データ数"""
    VIDEO_DURATION = "video_duration"
    """動画の長さ（秒）"""

    def get_display_name(self) -> str:
        """
        表示用の名称を取得する。
        """
        display_names = {
            AggregationUnit.TASK: "タスク数",
            AggregationUnit.INPUT_DATA: "入力データ数",
            AggregationUnit.VIDEO_DURATION: "動画の長さ（秒）",
        }
        return display_names[self]


def isoduration_to_second(duration: str) -> float:
    """
    ISO 8601 duration を 秒に変換する
    """
    return isodate.parse_duration(duration).total_seconds()


class TaskStatusForSummary(Enum):
    """
    Annofabユーザーがタスクについて知りたい粒度でまとめて分解した、タスクの状態。
    """

    NEVER_WORKED_UNASSIGNED = "never_worked.unassigned"
    """一度も作業していない状態かつ担当者未割り当て"""
    NEVER_WORKED_ASSIGNED = "never_worked.assigned"
    """一度も作業していない状態かつ担当者割り当て済み"""
    WORKED_NOT_REJECTED = "worked.not_rejected"
    """タスクのstatusは作業中または休憩中 AND 次のフェーズでまだ差し戻されていない（次のフェーズに進んでいない）"""
    WORKED_REJECTED = "worked.rejected"
    """タスクのstatusは作業中または休憩中 AND 次のフェーズで差し戻された"""
    ON_HOLD = "on_hold"
    """保留中"""
    COMPLETE = "complete"
    """完了"""

    @staticmethod
    def _get_not_started_status(task: Task, task_history_list: list[dict[str, Any]], not_worked_threshold_second: float) -> "TaskStatusForSummary":
        """
        NOT_STARTED状態のタスクについて、一度も作業されていないか、差し戻されて未着手かを判定する。

        Args:
            task: タスク情報
            task_history_list: タスク履歴のリスト
            not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）。この値以下なら作業していないとみなす。
        """
        # `number_of_inspections=1`を指定する理由：多段検査を無視して、検査フェーズが１回目かどうかを知りたいため
        step = get_step_for_current_phase(task, number_of_inspections=1)
        if step == 1:
            phase = task["phase"]
            worktime_second = sum(isoduration_to_second(history["accumulated_labor_time_milliseconds"]) for history in task_history_list if history["phase"] == phase)
            if worktime_second <= not_worked_threshold_second:
                # 一度も作業されていない（または閾値以下の作業時間）
                account_id = task["account_id"]
                if account_id is None:
                    return TaskStatusForSummary.NEVER_WORKED_UNASSIGNED
                else:
                    return TaskStatusForSummary.NEVER_WORKED_ASSIGNED
            else:
                return TaskStatusForSummary.WORKED_NOT_REJECTED
        else:
            return TaskStatusForSummary.WORKED_NOT_REJECTED

    @staticmethod
    def _get_working_or_break_status(task: Task) -> "TaskStatusForSummary":
        """
        WORKINGまたはBREAK状態のタスクについて、rejectされているかどうかを判定する。
        """
        # `number_of_inspections=1`を指定する理由：多段検査を無視して、検査フェーズが１回目かどうかを知りたいため
        step = get_step_for_current_phase(task, number_of_inspections=1)
        if step == 1:
            return TaskStatusForSummary.WORKED_NOT_REJECTED
        else:
            return TaskStatusForSummary.WORKED_REJECTED

    @staticmethod
    def from_task(task: dict[str, Any], task_history_list: list[dict[str, Any]], not_worked_threshold_second: float = 0) -> "TaskStatusForSummary":
        """
        タスク情報(dict)からインスタンスを生成します。

        Args:
            task: APIから取得したタスク情報. 以下のkeyが必要です。
                * status
                * phase
                * phase_stage
                * histories_by_phase
                * account_id
            task_history_list: タスク履歴のリスト
            not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）。この値以下なら作業していないとみなす。

        """
        status = TaskStatus(task["status"])
        match status:
            case TaskStatus.COMPLETE:
                return TaskStatusForSummary.COMPLETE

            case TaskStatus.ON_HOLD:
                return TaskStatusForSummary.ON_HOLD

            case TaskStatus.NOT_STARTED:
                return TaskStatusForSummary._get_not_started_status(task, task_history_list, not_worked_threshold_second)

            case TaskStatus.BREAK | TaskStatus.WORKING:
                return TaskStatusForSummary._get_working_or_break_status(task)

            case _:
                raise RuntimeError(f"'{status}'は対象外です。")


def get_step_for_current_phase(task: Task, number_of_inspections: int) -> int:
    """
    今のフェーズが何回目かを取得する。

    Args:
        task: 対象タスクの情報。phase, phase_stage, histories_by_phase を含む。
        number_of_inspections: 対象プロジェクトの検査フェーズの回数

    Returns:
        現在のフェーズのステップ数
    """
    current_phase = TaskPhase(task["phase"])
    current_phase_stage = task["phase_stage"]
    histories_by_phase = task["histories_by_phase"]

    number_of_rejections_by_acceptance = get_number_of_rejections(histories_by_phase, phase=TaskPhase.ACCEPTANCE)
    match current_phase:
        case TaskPhase.ACCEPTANCE:
            return number_of_rejections_by_acceptance + 1

        case TaskPhase.ANNOTATION:
            number_of_rejections_by_inspection = sum(
                get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage) for phase_stage in range(1, number_of_inspections + 1)
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        case TaskPhase.INSPECTION:
            number_of_rejections_by_inspection = sum(
                get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage) for phase_stage in range(current_phase_stage, number_of_inspections + 1)
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        case _ as unreachable:
            assert_noreturn(unreachable)


def create_df_task(
    task_list: list[dict[str, Any]], task_history_dict: dict[str, list[dict[str, Any]]], not_worked_threshold_second: float = 0, metadata_keys: list[str] | None = None
) -> pandas.DataFrame:
    """
    以下の列が含まれたタスクのDataFrameを生成します。
     * task_id
     * phase
     * task_status_for_summary
     * input_data_count
     * video_duration_second
     * metadata.{key} (metadata_keysで指定された各キー)

    Args:
        task_list: タスク情報のlist
        task_history_dict: タスクIDをキーとしたタスク履歴のdict
        not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）
        metadata_keys: 集計対象のメタデータキーのリスト

    Returns:
        タスク情報のDataFrame
    """
    metadata_keys = metadata_keys or []

    for task in task_list:
        task_history = task_history_dict[task["task_id"]]
        task["task_status_for_summary"] = TaskStatusForSummary.from_task(task, task_history, not_worked_threshold_second).value

        # 入力データ数を計算
        task["input_data_count"] = len(task.get("input_data_id_list", []))

        # 動画の長さを計算（秒）
        video_duration_second = 0
        for input_data_id in task.get("input_data_id_list", []):
            input_data = task.get("_input_data_dict", {}).get(input_data_id, {})
            system_metadata = input_data.get("system_metadata", {})
            if "duration_seconds" in system_metadata:
                video_duration_second += system_metadata["duration_seconds"]
        task["video_duration_second"] = video_duration_second

        # メタデータの値を抽出
        metadata = task.get("metadata", {})
        for key in metadata_keys:
            task[f"metadata.{key}"] = metadata.get(key, "")

    columns = ["task_id", "phase", "input_data_count", "video_duration_second"] + [f"metadata.{key}" for key in metadata_keys] + ["task_status_for_summary"]
    df = pandas.DataFrame(task_list, columns=columns)
    return df


def aggregate_df(df: pandas.DataFrame, metadata_keys: list[str] | None = None, unit: AggregationUnit = AggregationUnit.TASK) -> pandas.DataFrame:
    """
    タスクのフェーズとステータスごとに、指定された単位で集計する。

    Args:
        df: 以下の列を持つDataFrame
            * phase
            * task_status_for_summary
            * input_data_count
            * video_duration_second
            * metadata.{key} (metadata_keysで指定された各キー)
        metadata_keys: 集計対象のメタデータキーのリスト
        unit: 集計の単位

    Returns:
        indexがphase(とmetadata.*列),列がtask_status_for_summaryであるDataFrame
    """
    metadata_keys = metadata_keys or []
    metadata_columns = [f"metadata.{key}" for key in metadata_keys]

    # 集計対象の列を選択
    match unit:
        case AggregationUnit.TASK:
            df["_aggregate_value"] = 1
        case AggregationUnit.INPUT_DATA:
            df["_aggregate_value"] = df["input_data_count"]
        case AggregationUnit.VIDEO_DURATION:
            df["_aggregate_value"] = df["video_duration_second"]
        case _:
            raise ValueError(f"不正なunitです: {unit}")

    index_columns = ["phase", *metadata_columns]
    df2 = df.pivot_table(values="_aggregate_value", index=index_columns, columns="task_status_for_summary", aggfunc="sum", fill_value=0)

    # 列数を固定する
    for status in TaskStatusForSummary:
        if status.value not in df2.columns:
            df2[status.value] = 0

    # ソート処理
    sorted_phase = [
        TaskPhase.ANNOTATION.value,
        TaskPhase.INSPECTION.value,
        TaskPhase.ACCEPTANCE.value,
    ]

    if len(metadata_columns) > 0:
        # メタデータ列がある場合は、phase列でソートし、その後メタデータ列でソート
        df2 = df2.reset_index()
        df2["_phase_order"] = df2["phase"].map(lambda x: sorted_phase.index(x) if x in sorted_phase else len(sorted_phase))
        df2 = df2.sort_values(["_phase_order", *metadata_columns])
        df2 = df2.drop(columns=["_phase_order"])
    else:
        # メタデータ列がない場合は既存のロジック
        new_index = sorted(df2.index, key=lambda x: sorted_phase.index(x) if x in sorted_phase else len(sorted_phase))
        df2 = df2.loc[new_index]
        df2 = df2.reset_index()

    # 列の順序を設定
    result_columns = [
        "phase",
        *metadata_columns,
        TaskStatusForSummary.NEVER_WORKED_UNASSIGNED.value,
        TaskStatusForSummary.NEVER_WORKED_ASSIGNED.value,
        TaskStatusForSummary.WORKED_NOT_REJECTED.value,
        TaskStatusForSummary.WORKED_REJECTED.value,
        TaskStatusForSummary.ON_HOLD.value,
        TaskStatusForSummary.COMPLETE.value,
    ]
    df2 = df2[result_columns]
    return df2


class GettingTaskCountSummary:
    """
    タスク数のサマリーを取得するクラス
    """

    def __init__(
        self,
        annofab_service: AnnofabResource,
        project_id: str,
        *,
        temp_dir: Path | None = None,
        should_execute_get_tasks_api: bool = False,
        not_worked_threshold_second: float = 0,
        metadata_keys: list[str] | None = None,
        unit: AggregationUnit = AggregationUnit.TASK,
    ) -> None:
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.temp_dir = temp_dir
        self.should_execute_get_tasks_api = should_execute_get_tasks_api
        self.not_worked_threshold_second = not_worked_threshold_second
        self.metadata_keys = metadata_keys or []
        self.unit = unit

    def create_df_task(self) -> pandas.DataFrame:
        """
        以下の列が含まれたタスクのDataFrameを生成します。
        * task_id
        * phase
        * task_status_for_summary
        * metadata.{key} （metadata_keys で指定した各メタデータキーに対応する列）
        """
        if self.should_execute_get_tasks_api:
            task_list = self.annofab_service.wrapper.get_all_tasks(self.project_id)
            task_history_dict = {}
            for index, task in enumerate(task_list, start=1):
                task_id = task["task_id"]
                task_history_dict[task_id], _ = self.annofab_service.api.get_task_histories(self.project_id, task_id)
                if index % 100 == 0:
                    logger.info(f"{index} 件目のタスク履歴を取得しました。")

        else:
            task_list = self.get_task_list_with_downloading()
            task_history_dict = self.get_task_history_with_downloading()

        df = create_df_task(task_list, task_history_dict, self.not_worked_threshold_second, self.metadata_keys)
        return df

    def _get_task_list_with_downloading(self, temp_dir: Path) -> list[dict[str, Any]]:
        downloading_obj = DownloadingFile(self.annofab_service)
        task_json = downloading_obj.download_task_json_to_dir(self.project_id, temp_dir)
        with task_json.open(encoding="utf-8") as f:
            return json.load(f)

    def _get_task_history_with_downloading(self, temp_dir: Path) -> dict[str, list[dict[str, Any]]]:
        downloading_obj = DownloadingFile(self.annofab_service)
        task_history_json = downloading_obj.download_task_history_json_to_dir(self.project_id, temp_dir)
        with task_history_json.open(encoding="utf-8") as f:
            return json.load(f)

    def get_task_list_with_downloading(self) -> list[dict[str, Any]]:
        """
        タスク全件ファイルをダウンロードしてタスク情報を取得する。
        """
        if self.temp_dir is not None:
            return self._get_task_list_with_downloading(self.temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                return self._get_task_list_with_downloading(Path(str_temp_dir))

    def get_task_history_with_downloading(self) -> dict[str, list[dict[str, Any]]]:
        """
        タスク履歴全件ファイルをダウンロードしてタスク情報を取得する。
        """
        if self.temp_dir is not None:
            return self._get_task_history_with_downloading(self.temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                return self._get_task_history_with_downloading(Path(str_temp_dir))


class ListTaskCountByPhase(CommandLine):
    """
    フェーズごとのタスク数を一覧表示する。
    """

    def list_task_count_by_phase(
        self,
        project_id: str,
        *,
        temp_dir: Path | None = None,
        should_execute_get_tasks_api: bool = False,
        not_worked_threshold_second: float = 0,
        metadata_keys: list[str] | None = None,
        unit: AggregationUnit = AggregationUnit.TASK,
    ) -> None:
        """
        フェーズごとのタスク数をCSV形式で出力する。

        Args:
            project_id: プロジェクトID
            temp_dir: 一時ファイルの保存先ディレクトリ
            should_execute_get_tasks_api: getTasks APIを実行するかどうか
            not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）
            metadata_keys: 集計対象のメタデータキーのリスト
            unit: 集計の単位
        """
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        unit_name = unit.get_display_name()
        logger.info(f"project_id='{project_id}' :: フェーズごとの{unit_name}を集計します。")

        getting_obj = GettingTaskCountSummary(
            self.service,
            project_id,
            temp_dir=temp_dir,
            should_execute_get_tasks_api=should_execute_get_tasks_api,
            not_worked_threshold_second=not_worked_threshold_second,
            metadata_keys=metadata_keys,
            unit=unit,
        )
        df_task = getting_obj.create_df_task()

        if len(df_task) == 0:
            logger.info("タスクが0件ですが、ヘッダ行を出力します。")
            # aggregate_df関数と同じ列構成の空のDataFrameを作成
            metadata_columns = [f"metadata.{key}" for key in (metadata_keys or [])]
            result_columns = [
                "phase",
                *metadata_columns,
                TaskStatusForSummary.NEVER_WORKED_UNASSIGNED.value,
                TaskStatusForSummary.NEVER_WORKED_ASSIGNED.value,
                TaskStatusForSummary.WORKED_NOT_REJECTED.value,
                TaskStatusForSummary.WORKED_REJECTED.value,
                TaskStatusForSummary.ON_HOLD.value,
                TaskStatusForSummary.COMPLETE.value,
            ]
            df_summary = pandas.DataFrame(columns=result_columns)
        else:
            logger.info(f"{len(df_task)} 件のタスクを集計しました。")
            df_summary = aggregate_df(df_task, metadata_keys, unit)

        self.print_csv(df_summary)
        logger.info(f"project_id='{project_id}' :: フェーズごとの{unit_name}をCSV形式で出力しました。")

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        temp_dir = Path(args.temp_dir) if args.temp_dir is not None else None

        unit = AggregationUnit(args.unit)
        self.list_task_count_by_phase(
            project_id,
            temp_dir=temp_dir,
            should_execute_get_tasks_api=args.execute_get_tasks_api,
            not_worked_threshold_second=args.not_worked_threshold_second,
            metadata_keys=args.metadata_key,
            unit=unit,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--execute_get_tasks_api",
        action="store_true",
        help="タスク全件ファイルをダウンロードせずに、`getTasks` APIを実行してタスク一覧を取得します。`getTasks` APIを複数回実行するので、タスク全件ファイルをダウンロードするよりも時間がかかります。",
    )

    parser.add_argument(
        "--temp_dir",
        type=str,
        help="指定したディレクトリに、一時ファイルをダウンロードします。",
    )

    parser.add_argument(
        "--not_worked_threshold_second",
        type=float,
        default=0,
        help="作業していないとみなす作業時間の閾値を秒単位で指定します。この値以下の作業時間のタスクは、作業していないとみなします。",
    )

    parser.add_argument(
        "--metadata_key",
        type=str,
        nargs="+",
        help="集計対象のメタデータキーを指定します。指定したキーの値でグループ化してタスク数を集計します。",
    )

    parser.add_argument(
        "--unit",
        type=str,
        choices=["task", "input_data", "video_duration"],
        default="task",
        help="集計の単位を指定します。task: タスク数、input_data: 入力データ数、video_duration: 動画の長さ（秒）。デフォルトは task です。",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskCountByPhase(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_by_phase"
    subcommand_help = "フェーズごとのタスク数をCSV形式で出力します。"
    epilog = "オーナロールまたはアノテーションユーザーロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
