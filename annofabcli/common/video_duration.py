from __future__ import annotations

import argparse
import datetime
import json
import logging
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Literal, TypedDict

import pandas
from annofabapi.models import InputData, InputDataType, ProjectMemberRole, Task

from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_according_to_format, print_csv
from annofabcli.common.video_duration_histogram import BIN_COUNT, TimeUnit, plot_video_duration

logger = logging.getLogger(__name__)

ResourceUnit = Literal["task", "input_data"]
"""動画長を数える単位。"""


class TaskVideoDuration(TypedDict):
    project_id: str
    task_id: str
    phase: str
    phase_stage: int
    status: str
    input_data_id: str
    input_data_name: str | None
    video_duration_second: float | None
    input_data_updated_datetime: str | None


TASK_VIDEO_DURATION_COLUMNS = list(TaskVideoDuration.__annotations__)
"""タスクの動画長一覧のCSV列。0件の場合も出力する。"""


def get_task_video_duration_list(task_list: Collection[Task], input_data_list: Collection[InputData]) -> list[TaskVideoDuration]:
    """タスクごとの動画長を取得します。同じ入力データもタスクごとに数えます。

    Args:
        task_list: 対象タスク。
        input_data_list: 入力データ。

    Returns:
        タスクごとの動画長。取得できない値はNoneです。
    """
    input_data_by_id = {data["input_data_id"]: data for data in input_data_list}
    result: list[TaskVideoDuration] = []
    for task in task_list:
        if len(task["input_data_id_list"]) != 1:
            raise ValueError(f"task_id='{task['task_id']}'の入力データ数が1ではありません。動画タスクを指定してください。")
        input_data_id = task["input_data_id_list"][0]
        data = input_data_by_id.get(input_data_id)
        duration = data["system_metadata"]["input_duration"] if data is not None else None
        if duration is None:
            logger.warning(f"task_id='{task['task_id']}', input_data_id='{input_data_id}'の動画長を取得できません。")
        result.append(
            TaskVideoDuration(
                project_id=task["project_id"],
                task_id=task["task_id"],
                phase=task["phase"],
                phase_stage=task["phase_stage"],
                status=task["status"],
                input_data_id=input_data_id,
                input_data_name=data["input_data_name"] if data is not None else None,
                video_duration_second=duration,
                input_data_updated_datetime=data["updated_datetime"] if data is not None else None,
            )
        )
    return result


def print_task_video_duration_list(rows: list[TaskVideoDuration], output_format: OutputFormat, output_file: Path | None) -> None:
    """CSVとJSONで同じ項目の動画長一覧を出力します。

    Args:
        rows: 出力する一覧。
        output_format: 出力形式。
        output_file: 出力先。Noneなら標準出力。

    Returns:
        None。
    """
    if output_format == OutputFormat.CSV:
        print_csv(pandas.DataFrame(rows, columns=TASK_VIDEO_DURATION_COLUMNS), output=output_file)
    else:
        print_according_to_format(rows, format=output_format, output=output_file)


def get_video_durations(
    task_list: Collection[Task],
    input_data_list: Collection[InputData],
    *,
    resource_unit: ResourceUnit,
    task_ids: Collection[str] | None = None,
    input_data_ids: Collection[str] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> tuple[list[float], int]:
    """可視化する動画長と除外件数を取得します。

    Args:
        task_list: タスク。
        input_data_list: 入力データ。
        resource_unit: 集計単位。
        task_ids: 対象タスクID。
        input_data_ids: 対象入力データID。
        from_date: 入力データ更新日の下限（当日を含む）。
        to_date: 入力データ更新日の上限（当日を含む）。

    Returns:
        動画長の一覧と、動画長を取得できなかった件数。
    """
    tasks = [task for task in task_list if task_ids is None or task["task_id"] in task_ids]
    data_list = list(input_data_list)
    if input_data_ids is not None:
        data_list = [data for data in data_list if data["input_data_id"] in input_data_ids]
    if from_date is not None:
        lower = datetime.date.fromisoformat(from_date)
        data_list = [data for data in data_list if datetime.datetime.fromisoformat(data["updated_datetime"]).date() >= lower]
    if to_date is not None:
        upper = datetime.date.fromisoformat(to_date)
        data_list = [data for data in data_list if datetime.datetime.fromisoformat(data["updated_datetime"]).date() <= upper]
    if resource_unit == "task":
        if input_data_ids is not None or from_date is not None or to_date is not None:
            selected_ids = {data["input_data_id"] for data in data_list}
            tasks = [task for task in tasks if any(data_id in selected_ids for data_id in task["input_data_id_list"])]
        values = [row["video_duration_second"] for row in get_task_video_duration_list(tasks, data_list)]
    else:
        if task_ids is not None:
            selected_ids = {data_id for task in tasks for data_id in task["input_data_id_list"]}
            data_list = [data for data in data_list if data["input_data_id"] in selected_ids]
        values = [data["system_metadata"]["input_duration"] for data in data_list]
    durations = [value for value in values if value is not None]
    return durations, len(values) - len(durations)


class VideoDurationCommand(CommandLine):
    def run(self, resource_unit: ResourceUnit, *, visualize: bool) -> None:
        """動画プロジェクトの情報を読み取り、一覧または分布を出力します。

        Args:
            resource_unit: 集計単位。
            visualize: 分布をHTMLに出力するか。

        Returns:
            None。
        """
        args = self.args
        needs_tasks = resource_unit == "task" or args.task_id is not None
        project_title = None
        if args.project_id is not None:
            self.require_project_access(args.project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(args.project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                raise AnnofabCliException("動画プロジェクトを指定してください。")
            project_title = project["title"]
        with tempfile.TemporaryDirectory() as temporary_dir:
            temp_dir = args.temp_dir if args.temp_dir is not None else Path(temporary_dir)
            downloading = DownloadingFile(self.service)
            input_data_json = args.input_data_json
            if input_data_json is None:
                input_data_json = downloading.download_input_data_json_to_dir(args.project_id, temp_dir, is_latest=args.latest)
            with input_data_json.open(encoding="utf-8") as file:
                input_data_list = json.load(file)
            task_list = []
            if needs_tasks:
                task_json = args.task_json
                if task_json is None:
                    task_json = downloading.download_task_json_to_dir(args.project_id, temp_dir, is_latest=args.latest)
                with task_json.open(encoding="utf-8") as file:
                    task_list = json.load(file)
        task_ids = get_list_from_args(args.task_id) if args.task_id is not None else None
        if visualize:
            durations, excluded_count = get_video_durations(
                task_list,
                input_data_list,
                resource_unit=resource_unit,
                task_ids=task_ids,
                input_data_ids=get_list_from_args(args.input_data_id) if args.input_data_id is not None else None,
                from_date=args.from_date,
                to_date=args.to_date,
            )
            logger.info(f"{len(durations)}件を可視化します。動画長が不明なため除外した件数: {excluded_count}件")
            plot_video_duration(
                durations,
                args.output,
                time_unit=TimeUnit(args.time_unit),
                bin_width=args.bin_width,
                project_id=args.project_id,
                project_title=project_title,
                y_axis_label="タスク数" if resource_unit == "task" else "入力データ数",
                excluded_count=excluded_count,
            )
        else:
            tasks = [task for task in task_list if task_ids is None or task["task_id"] in task_ids]
            rows = get_task_video_duration_list(tasks, input_data_list)
            logger.info(f"{len(rows)}件のタスクの動画長を出力します。")
            print_task_video_duration_list(rows, OutputFormat(args.format), args.output)


def run_command(args: argparse.Namespace, resource_unit: ResourceUnit, *, visualize: bool) -> None:
    """認証後に動画長コマンドを実行します。

    Args:
        args: コマンドライン引数。
        resource_unit: 集計単位。
        visualize: HTMLを出力するか。

    Returns:
        None。
    """
    needs_tasks = resource_unit == "task" or args.task_id is not None
    if args.project_id is None and (args.input_data_json is None or (needs_tasks and args.task_json is None)):
        raise AnnofabCliException("必要なJSONファイルが未指定のときは、--project_idを指定してください。")
    service = build_annofabapi_resource_and_login(args)
    VideoDurationCommand(service, AnnofabApiFacade(service), args).run(resource_unit, visualize=visualize)


def add_arguments(parser: argparse.ArgumentParser, *, visualize: bool) -> None:
    """動画長コマンドの共通引数を登録します。

    Args:
        parser: 引数パーサー。
        visualize: 可視化用引数を登録するか。

    Returns:
        None。
    """
    arguments = ArgumentParser(parser)
    parser.add_argument("-p", "--project_id", help="対象の動画プロジェクトID。必要なJSONファイルをすべて指定した場合は省略できます。")
    parser.add_argument("--input_data_json", type=Path, help="input_data downloadで取得した入力データのJSONファイル。")
    parser.add_argument("--task_json", type=Path, help="task downloadで取得したタスクのJSONファイル。入力データ単位では、--task_id指定時のみ必要です。")
    parser.add_argument("--latest", action="store_true", help="入力データ情報とタスク情報の最新版を取得します。数分待つ場合があります。")
    parser.add_argument("--temp_dir", type=Path, help="JSONファイルをダウンロードするディレクトリ。")
    parser.add_argument("-t", "--task_id", nargs="+", help="対象タスクID。file://でID一覧ファイルを指定できます。")
    if visualize:
        parser.add_argument("-o", "--output", type=Path, required=True, help="出力先HTMLファイル。")
        parser.add_argument("-i", "--input_data_id", nargs="+", help="対象入力データID。file://でID一覧ファイルを指定できます。")
        parser.add_argument("--time_unit", choices=[unit.value for unit in TimeUnit], default=TimeUnit.SECOND.value, help="横軸の時間単位。")
        parser.add_argument("--bin_width", type=float, help=f"ビンの幅（秒）。省略すると{BIN_COUNT}個のビンを使用します。正の値を指定してください。")
        parser.add_argument("--from_date", help="この日以降に更新された入力データを対象にします（YYYY-MM-DD、当日を含む）。")
        parser.add_argument("--to_date", help="この日以前に更新された入力データを対象にします（YYYY-MM-DD、当日を含む）。")
    else:
        arguments.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
        arguments.add_output()
