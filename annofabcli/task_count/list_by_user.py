import argparse
import json
import logging
import tempfile
from enum import Enum
from pathlib import Path

import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskPhase, TaskStatus
from annofabapi.project_member_repository import ProjectMemberRepository

import annofabcli.common.cli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_count.common import SUMMARY_COLUMNS

logger = logging.getLogger(__name__)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
DEFAULT_TASK_ID_DELIMITER = "_"
UNASSIGNED_ACCOUNT_ID = "__unassigned__"
UNASSIGNED_USER_ID = "unassigned"


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


def add_info_to_task(task: Task, metadata_keys: list[str] | None = None) -> Task:
    """タスクに集計用の情報を追加する。

    Args:
        task: タスク情報。
        metadata_keys: 集計対象のタスクメタデータキー。

    Returns:
        集計用の情報を追加したタスク情報。
    """
    task["status_for_summary"] = TaskStatusForSummary.from_task(task).value
    match task["status"]:
        case TaskStatus.NOT_STARTED.value:
            summary_status = "never_worked"
        case TaskStatus.WORKING.value | TaskStatus.BREAK.value:
            summary_status = "worked"
        case TaskStatus.ON_HOLD.value:
            summary_status = "on_hold"
        case TaskStatus.COMPLETE.value:
            summary_status = "complete"
        case _:
            raise RuntimeError(f"status={task['status']}が対象外です。")

    summary_phase = TaskPhase.ACCEPTANCE.value if summary_status == "complete" else task["phase"]
    task["summary_column"] = f"{summary_phase}.{summary_status}"
    task["account_id"] = task.get("account_id") or UNASSIGNED_ACCOUNT_ID
    metadata = task.get("metadata") or {}
    for key in metadata_keys or []:
        task[f"metadata.{key}"] = metadata.get(key)
    return task


def create_task_count_summary_df(task_list: list[Task], metadata_keys: list[str] | None = None) -> pandas.DataFrame:
    """タスク数の集計結果が格納されたDataFrameを取得する。

    Args:
        task_list: タスク情報のリスト。
        metadata_keys: 集計対象のタスクメタデータキー。

    Returns:
        ユーザとタスクメタデータごとのタスク数を、フェーズと状態別に格納したDataFrame。
    """

    metadata_columns = [f"metadata.{key}" for key in metadata_keys or []]
    result_columns = ["account_id", *metadata_columns, *SUMMARY_COLUMNS]
    if len(task_list) == 0:
        return pandas.DataFrame(columns=result_columns)

    df_task = pandas.DataFrame([add_info_to_task(task, metadata_keys) for task in task_list])
    index_columns = ["account_id", *metadata_columns]
    df_summary = df_task.pivot_table(
        values="task_id",
        index=index_columns,
        columns="summary_column",
        aggfunc="count",
        fill_value=0,
        dropna=False,
    ).reset_index()
    for column in SUMMARY_COLUMNS:
        if column not in df_summary.columns:
            df_summary[column] = 0

    return df_summary.loc[df_summary[SUMMARY_COLUMNS].sum(axis="columns") > 0, result_columns]


def create_legacy_task_count_summary_df(task_list: list[Task]) -> pandas.DataFrame:
    """非推奨コマンドと互換性のあるタスク数の集計結果を生成する。

    Args:
        task_list: タスク情報のリスト。

    Returns:
        従来形式で集計したDataFrame。
    """
    records = []
    for task in task_list:
        record = dict(task)
        record["status_for_summary"] = TaskStatusForSummary.from_task(task).value
        records.append(record)

    df_task = pandas.DataFrame(records)
    df_summary = df_task.pivot_table(
        values="task_id",
        index=["account_id"],
        columns=["status_for_summary"],
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    for status in TaskStatusForSummary:
        if status.value not in df_summary.columns:
            df_summary[status.value] = 0
    return df_summary


class ListTaskCountByUser(CommandLine):
    def create_user_df(self, project_id: str, account_id_list: list[str], *, include_unknown_account: bool = True) -> pandas.DataFrame:
        project_member_repository = ProjectMemberRepository(self.service)
        user_list = []
        for account_id in account_id_list:
            try:
                user = project_member_repository.get_project_member_from_account_id(project_id=project_id, account_id=account_id)
                user_list.append(user)
            except ValueError:
                logger.warning(f"account_id='{account_id}'であるユーザーは、project_id='{project_id}'のプロジェクトのメンバーではありません。")
                if include_unknown_account:
                    user_list.append({"account_id": account_id, "user_id": account_id, "username": "", "biography": ""})
        return pandas.DataFrame(user_list, columns=["account_id", "user_id", "username", "biography"])

    def create_summary_df(self, project_id: str, task_list: list[Task], metadata_keys: list[str] | None = None) -> pandas.DataFrame:
        df_task_count = create_task_count_summary_df(task_list, metadata_keys)
        account_id_list = df_task_count.loc[df_task_count["account_id"] != UNASSIGNED_ACCOUNT_ID, "account_id"].to_list()
        df_user = self.create_user_df(project_id, account_id_list)
        if UNASSIGNED_ACCOUNT_ID in df_task_count["account_id"].array:
            df_unassigned_user = pandas.DataFrame([{"account_id": UNASSIGNED_ACCOUNT_ID, "user_id": UNASSIGNED_USER_ID, "username": "", "biography": ""}])
            df_user = pandas.concat([df_user, df_unassigned_user], ignore_index=True)

        df = pandas.merge(df_user, df_task_count, how="left", on=["account_id"])
        return df

    def create_legacy_summary_df(self, project_id: str, task_list: list[Task]) -> pandas.DataFrame:
        """非推奨コマンドと互換性のあるユーザ別集計結果を生成する。

        Args:
            project_id: プロジェクトID。
            task_list: タスク情報のリスト。

        Returns:
            従来形式で集計したDataFrame。
        """
        df_task_count = create_legacy_task_count_summary_df(task_list)
        df_user = self.create_user_df(project_id, df_task_count["account_id"], include_unknown_account=False)
        if len(df_user) == 0:
            return pandas.DataFrame()

        df = pandas.merge(df_user, df_task_count, how="left", on=["account_id"])
        task_count_columns = [status.value for status in TaskStatusForSummary]
        df[task_count_columns] = df[task_count_columns].fillna(0)
        return df

    def print_summarize_df(self, df: pandas.DataFrame, metadata_keys: list[str] | None = None) -> None:
        metadata_columns = [f"metadata.{key}" for key in metadata_keys or []]
        columns = ["user_id", "username", "biography", *metadata_columns, *SUMMARY_COLUMNS]
        target_df = df[columns].sort_values(["user_id", *metadata_columns])
        annofabcli.common.utils.print_according_to_format(
            target_df,
            format=OutputFormat.CSV,
            output=self.output,
        )

    def print_legacy_summarize_df(self, df: pandas.DataFrame) -> None:
        """非推奨コマンドと互換性のある列をCSV形式で出力する。

        Args:
            df: 出力対象のDataFrame。

        Returns:
            None
        """
        columns = ["user_id", "username", "biography", *[status.value for status in TaskStatusForSummary]]
        target_df = df[columns].sort_values("user_id")
        annofabcli.common.utils.print_according_to_format(
            target_df,
            format=OutputFormat.CSV,
            output=self.output,
        )

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        def download_and_process_task_data(temp_dir: Path) -> None:
            if args.task_json is not None:
                task_json_path = args.task_json
            else:
                downloading_obj = DownloadingFile(self.service)
                task_json_path = downloading_obj.download_task_json_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=args.latest,
                    wait_options=DEFAULT_WAIT_OPTIONS,
                )

            with open(task_json_path, encoding="utf-8") as f:  # noqa: PTH123
                task_list = json.load(f)

            if args.legacy_output:
                df = self.create_legacy_summary_df(project_id, task_list)
                if len(df) > 0:
                    self.print_legacy_summarize_df(df)
                else:
                    logger.error("出力対象データが0件のため、出力しません。")
                return

            df = self.create_summary_df(project_id, task_list, args.metadata_key)
            if len(df) == 0:
                logger.info("タスクが0件ですが、ヘッダ行を出力します。")
            self.print_summarize_df(df, args.metadata_key)

        if args.temp_dir is not None:
            download_and_process_task_data(temp_dir=args.temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                download_and_process_task_data(temp_dir=Path(str_temp_dir))


def parse_args(parser: argparse.ArgumentParser, *, include_metadata_key: bool = True) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    if include_metadata_key:
        parser.add_argument(
            "--metadata_key",
            type=str,
            nargs="+",
            help="集計対象のタスクメタデータキーを指定します。指定したキーの値でグループ化してタスク数を集計します。",
        )
        parser.set_defaults(legacy_output=False)
    else:
        parser.set_defaults(metadata_key=None, legacy_output=True)

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

    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、一時ファイルをダウンロードします。",
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskCountByUser(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_by_user"
    subcommand_help = "ユーザごとに、担当しているタスク数を出力します。"
    description = "ユーザごとに、担当しているタスク数をCSV形式で出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
