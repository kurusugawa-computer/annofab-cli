from __future__ import annotations

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
from annofabcli.common.utils import print_according_to_format, print_csv

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `statistics summarize_task_count_by_user` コマンドは非推奨です。"
    "代わりに `task_count list_by_user` コマンドを使用してください。 "
    "`statistics summarize_task_count_by_user` コマンドは2027/01/01以降に廃止予定です。"
)

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)
"""タスク全件ファイルの生成を待つ設定。"""


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
    def from_task(task: Task) -> TaskStatusForSummary:
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
    """タスクに従来形式の集計用情報を追加する。

    Args:
        task: タスク情報。

    Returns:
        集計用の情報を追加したタスク情報。
    """
    task["status_for_summary"] = TaskStatusForSummary.from_task(task).value
    return task


def create_task_count_summary_df(task_list: list[Task]) -> pandas.DataFrame:
    """非推奨コマンドと互換性のあるタスク数の集計結果を生成する。

    Args:
        task_list: タスク情報のリスト。

    Returns:
        従来形式で集計したDataFrame。
    """
    if not task_list:
        return pandas.DataFrame(columns=["account_id", *[status.value for status in TaskStatusForSummary]])

    df_task = pandas.DataFrame([add_info_to_task(task) for task in task_list])
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


def print_task_count_summary(df: pandas.DataFrame, *, format: OutputFormat, output: str | Path | None = None) -> None:  # noqa: A002
    """集計結果を指定した形式で出力する。

    Args:
        df: 集計キーと集計値を列に持つ集計結果。
        format: 出力形式。
        output: 出力先。Noneなら標準出力に出力する。

    Returns:
        None
    """
    if format == OutputFormat.CSV:
        print_csv(df, output=output)
    else:
        # JSONでは欠損値をnullとして出力する。
        records = df.astype(object).where(df.notna(), None).to_dict(orient="records")
        print_according_to_format(records, format=format, output=output)


class SummarizeTaskCountByUser(CommandLine):
    def create_user_df(self, project_id: str, account_id_list: list[str]) -> pandas.DataFrame:
        project_member_repository = ProjectMemberRepository(self.service)
        user_list = []
        for account_id in account_id_list:
            try:
                user = project_member_repository.get_project_member_from_account_id(project_id=project_id, account_id=account_id)
                user_list.append(user)
            except ValueError:
                logger.warning(f"account_id='{account_id}'であるユーザーは、project_id='{project_id}'のプロジェクトのメンバーではありません。")
        return pandas.DataFrame(user_list, columns=["account_id", "user_id", "username", "biography"])

    def create_summary_df(self, project_id: str, task_list: list[Task]) -> pandas.DataFrame:
        """非推奨コマンドと互換性のあるユーザ別集計結果を生成する。

        Args:
            project_id: プロジェクトID。
            task_list: タスク情報のリスト。

        Returns:
            従来形式で集計したDataFrame。
        """
        df_task_count = create_task_count_summary_df(task_list)
        df_user = self.create_user_df(project_id, df_task_count["account_id"].to_list())
        df = pandas.merge(df_user, df_task_count, how="left", on=["account_id"])
        task_count_columns = [status.value for status in TaskStatusForSummary]
        df[task_count_columns] = df[task_count_columns].fillna(0)
        return df

    def print_summarize_df(self, df: pandas.DataFrame) -> None:
        """非推奨コマンドと互換性のある列を指定した形式で出力する。

        Args:
            df: 出力対象のDataFrame。

        Returns:
            None
        """
        columns = ["user_id", "username", "biography", *[status.value for status in TaskStatusForSummary]]
        target_df = df[columns].sort_values("user_id")
        print_task_count_summary(
            target_df,
            format=OutputFormat(self.str_format),
            output=self.output,
        )

    def main(self) -> None:
        """タスク一覧を読み込み、ユーザ別タスク数を出力する。

        Args:
            なし。

        Returns:
            None
        """
        args = self.args
        project_id = args.project_id
        self.require_project_access(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        def download_and_process_task_data(temp_dir: Path) -> None:
            if args.task_json_file is not None:
                task_json_path = args.task_json_file
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

            df = self.create_summary_df(project_id, task_list)
            self.print_summarize_df(df)

        if args.temp_dir is not None:
            download_and_process_task_data(temp_dir=args.temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                download_and_process_task_data(temp_dir=Path(str_temp_dir))


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--task_json_file",
        type=str,
        help="タスク情報が記載されたJSONファイルのパスを指定します。JSONファイルは ``$ annofabcli task download`` コマンドで取得できます。"
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

    parser.set_defaults(subcommand_func=main, format=OutputFormat.CSV.value)


def main(args: argparse.Namespace) -> None:
    """非推奨警告を出力してユーザ別タスク数を集計する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    logger.warning(DEPRECATED_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SummarizeTaskCountByUser(service, facade, args).main()


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """旧コマンドのサブパーサーを生成する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_name = "summarize_task_count_by_user"
    subcommand_help = f"ユーザごとに、担当しているタスク数を出力します。\n{DEPRECATED_MESSAGE}"
    description = f"ユーザごとに、担当しているタスク数をCSV形式で出力します。\n{DEPRECATED_MESSAGE}"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
