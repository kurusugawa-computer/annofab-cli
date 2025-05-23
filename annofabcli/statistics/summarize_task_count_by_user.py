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
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
DEFAULT_TASK_ID_DELIMITER = "_"


class TaskStatusForSummary(Enum):
    """
    TaskStatusのサマリー用（知りたい情報をstatusにしている）
    """

    ANNOTATION_NOT_STARTED = "annotation_not_started"
    """教師付未着手"""
    INSPECTION_NOT_STARTED = "inspection_not_started"
    """検査未着手"""
    ACCEPTANCE_NOT_STARTED = "acceptance_not_started"
    """受入未着手"""

    WORKING = "working"
    BREAK = "break"
    ON_HOLD = "on_hold"
    COMPLETE = "complete"

    @staticmethod
    def from_task(task: Task) -> "TaskStatusForSummary":
        status = task["status"]
        if status == TaskStatus.NOT_STARTED.value:
            phase = task["phase"]
            if phase == TaskPhase.ANNOTATION.value:
                return TaskStatusForSummary.ANNOTATION_NOT_STARTED
            elif phase == TaskPhase.INSPECTION.value:
                return TaskStatusForSummary.INSPECTION_NOT_STARTED
            elif phase == TaskPhase.ACCEPTANCE.value:
                return TaskStatusForSummary.ACCEPTANCE_NOT_STARTED
            else:
                raise RuntimeError(f"phase={phase}が対象外です。")
        else:
            return TaskStatusForSummary(status)


def add_info_to_task(task: Task) -> Task:
    task["status_for_summary"] = TaskStatusForSummary.from_task(task).value
    return task


def create_task_count_summary_df(task_list: list[Task]) -> pandas.DataFrame:
    """
    タスク数の集計結果が格納されたDataFrameを取得する。

    Args:
        task_list:

    Returns:

    """

    def add_columns_if_not_exists(df: pandas.DataFrame, column: str):  # noqa: ANN202
        if column not in df.columns:
            df[column] = 0

    df_task = pandas.DataFrame([add_info_to_task(t) for t in task_list])
    df_summary = df_task.pivot_table(values="task_id", index=["account_id"], columns=["status_for_summary"], aggfunc="count", fill_value=0).reset_index()
    for status in TaskStatusForSummary:
        add_columns_if_not_exists(df_summary, status.value)

    return df_summary


class SummarizeTaskCountByUser(CommandLine):
    def create_user_df(self, project_id: str, account_id_list: list[str]) -> pandas.DataFrame:
        user_list = []
        for account_id in account_id_list:
            user = self.facade.get_project_member_from_account_id(project_id=project_id, account_id=account_id)
            if user is not None:
                user_list.append(user)
        return pandas.DataFrame(user_list, columns=["account_id", "user_id", "username", "biography"])

    def create_summary_df(self, project_id: str, task_list: list[Task]) -> pandas.DataFrame:
        df_task_count = create_task_count_summary_df(task_list)
        df_user = self.create_user_df(project_id, df_task_count["account_id"])
        if len(df_user) == 0:
            return pandas.DataFrame()

        df = pandas.merge(df_user, df_task_count, how="left", on=["account_id"])
        task_count_columns = [s.value for s in TaskStatusForSummary]
        df[task_count_columns] = df[task_count_columns].fillna(0)
        return df

    def print_summarize_df(self, df: pandas.DataFrame) -> None:
        columns = ["user_id", "username", "biography"] + [status.value for status in TaskStatusForSummary]
        target_df = df[columns].sort_values("user_id")
        annofabcli.common.utils.print_according_to_format(
            target_df,
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

        df = self.create_summary_df(project_id, task_list)
        if len(df) > 0:
            self.print_summarize_df(df)
        else:
            logger.error("出力対象データが0件のため、出力しません。")


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定してます。JSONファイルは`$ annofabcli task download`コマンドで取得できます。"
        "指定しない場合は、Annofabからタスク全件ファイルをダウンロードします。",
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
    SummarizeTaskCountByUser(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "summarize_task_count_by_user"
    subcommand_help = "ユーザごとに、担当しているタスク数を出力します。"
    description = "ユーザごとに、担当しているタスク数をCSV形式で出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
