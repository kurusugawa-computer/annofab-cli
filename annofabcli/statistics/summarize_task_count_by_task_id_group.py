from __future__ import annotations

import argparse
import json
import logging
from enum import Enum
from typing import Optional

import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskPhase, TaskStatus

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.statistics.summarize_task_count import get_step_for_current_phase

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
TASK_ID_GROUP_UNKNOWN = "unknown"
"""task_id_groupが不明な場合に表示する値"""


class TaskStatusForSummary(Enum):
    """
    TaskStatusのサマリー用（知りたい情報をstatusにしている）
    """

    COMPLETE = "complete"
    ON_HOLD = "on_hold"
    ANNOTATION_NOT_STARTED = "annotation_not_started"
    """教師付作業されていない状態"""
    INSPECTION_NOT_STARTED = "inspection_not_started"
    """検査作業されていない状態"""
    ACCEPTANCE_NOT_STARTED = "acceptance_not_started"
    """受入作業されていない状態"""
    OTHER = "other"
    """休憩中/作業中/2回目移行の各フェーズの未着手状態"""

    @staticmethod
    def _get_not_started_status(task: Task) -> TaskStatusForSummary:
        # `number_of_inspections=1`を指定する理由：多段検査を無視して、検査フェーズが１回目かどうかを知りたいため
        step = get_step_for_current_phase(task, number_of_inspections=1)
        if step == 1:
            phase = TaskPhase(task["phase"])
            if phase == TaskPhase.ANNOTATION:
                return TaskStatusForSummary.ANNOTATION_NOT_STARTED
            elif phase == TaskPhase.INSPECTION:
                return TaskStatusForSummary.INSPECTION_NOT_STARTED
            elif phase == TaskPhase.ACCEPTANCE:
                return TaskStatusForSummary.ACCEPTANCE_NOT_STARTED
            else:
                raise ValueError(f"'{phase.value}'は対象外です。")
        else:
            return TaskStatusForSummary.OTHER

    @staticmethod
    def from_task(task: Task) -> TaskStatusForSummary:
        """
        タスク情報(dict)からインスタンスを生成します。
        Args:
            task: APIから取得したタスク情報. 以下のkeyが必要です。
                * status
                * phase
                * phase_stage
                * histories_by_phase

        """
        status = TaskStatus(task["status"])
        if status == TaskStatus.COMPLETE:
            return TaskStatusForSummary.COMPLETE

        elif status == TaskStatus.ON_HOLD:
            return TaskStatusForSummary.ON_HOLD

        elif status == TaskStatus.NOT_STARTED:
            return TaskStatusForSummary._get_not_started_status(task)
        else:
            # WORKING, BREAK
            return TaskStatusForSummary.OTHER


def get_task_id_prefix(task_id: str, delimiter: str) -> str:
    tmp_list = task_id.split(delimiter)
    if len(tmp_list) <= 1:
        return TASK_ID_GROUP_UNKNOWN
    else:
        return delimiter.join(tmp_list[0 : len(tmp_list) - 1])


def create_task_count_summary_df(task_list: list[Task], task_id_delimiter: Optional[str], task_id_groups: Optional[dict[str, list[str]]]) -> pandas.DataFrame:
    """
    タスク数を集計したDataFrameを生成する。

    Args:
        task_list:

    Returns:

    """

    def add_columns_if_not_exists(df: pandas.DataFrame, column: str):  # noqa: ANN202
        if column not in df.columns:
            df[column] = 0

    for task in task_list:
        task["status_for_summary"] = TaskStatusForSummary.from_task(task).value

    df_task = pandas.DataFrame(task_list)

    if task_id_groups is not None:
        df_tmp = pandas.DataFrame(
            [(task_id_group, task_id) for task_id_group, task_id_list in task_id_groups.items() for task_id in task_id_list],
            columns=("task_id_group", "task_id"),
        )
        df_task = df_task.merge(df_tmp, on="task_id", how="left")

    if task_id_delimiter is not None:
        df_task["task_id_group"] = df_task["task_id"].map(lambda e: get_task_id_prefix(e, delimiter=task_id_delimiter))

    df_task.fillna({"task_id_group": TASK_ID_GROUP_UNKNOWN}, inplace=True)

    df_summary = df_task.pivot_table(values="task_id", index=["task_id_group"], columns=["status_for_summary"], aggfunc="count", fill_value=0).reset_index()

    for status in TaskStatusForSummary:
        add_columns_if_not_exists(df_summary, status.value)

    df_summary["sum"] = df_task.pivot_table(values="task_id", index=["task_id_group"], aggfunc="count", fill_value=0).reset_index().fillna(0)["task_id"]

    return df_summary


class SummarizeTaskCountByTaskId(CommandLine):
    def print_summarize_task_count(self, df: pandas.DataFrame) -> None:
        columns = ["task_id_group"] + [status.value for status in TaskStatusForSummary] + ["sum"]
        annofabcli.common.utils.print_according_to_format(
            df[columns],
            format=FormatArgument(FormatArgument.CSV),
            output=self.output,
        )

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if args.task_json is not None:
            task_json_path = args.task_json
        else:
            cache_dir = annofabcli.common.utils.get_cache_dir()
            task_json_path = cache_dir / f"{project_id}-task.json"

            downloading_obj = DownloadingFile(self.service)
            downloading_obj.download_task_json(project_id, dest_path=str(task_json_path), is_latest=args.latest, wait_options=DEFAULT_WAIT_OPTIONS)

        with open(task_json_path, encoding="utf-8") as f:  # noqa: PTH123
            task_list = json.load(f)

        df = create_task_count_summary_df(task_list, task_id_delimiter=args.task_id_delimiter, task_id_groups=get_json_from_args(args.task_id_groups))
        self.print_summarize_task_count(df)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してます。JSONファイルは ``$ annofabcli task download`` コマンドで取得できます。"
        "指定しない場合は、Annofabからタスク全件ファイルをダウンロードします。",
    )

    task_id_group = parser.add_mutually_exclusive_group(required=True)

    task_id_group.add_argument(
        "--task_id_delimiter",
        type=str,
        help="task_idのprefixと連番を分ける区切り文字です。デフォルトは ``_`` で、 ``{prefix}_{連番}`` のようなtask_idを想定しています。",
    )

    task_id_group.add_argument(
        "--task_id_groups",
        type=str,
        help="keyがtask_id_group, valueがtask_idのlistであるJSON文字列を渡します。``file://`` を先頭に付けるとJSONファイルを指定できます。",
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="最新のタスク一覧ファイルを参照します。このオプションを指定すると、タスク一覧ファイルを更新するのに数分待ちます。",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeTaskCountByTaskId(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "summarize_task_count_by_task_id_group"
    subcommand_help = "task_idのグループごとにタスク数を集計します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
