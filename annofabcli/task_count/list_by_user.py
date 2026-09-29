import argparse
import json
import logging
import sys
import tempfile
from enum import Enum
from pathlib import Path

import pandas
from annofabapi.models import ProjectMemberRole, Task, TaskPhase, TaskStatus
from annofabapi.project_member_repository import ProjectMemberRepository

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_count.common import SUMMARY_COLUMNS, summarize_df_task
from annofabcli.task_count.list_by_phase import AggregationUnit, GettingTaskCountSummary

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


def summarize_df_task_by_user(
    df_task: pandas.DataFrame,
    metadata_keys: list[str] | None = None,
    unit: AggregationUnit = AggregationUnit.TASK,
) -> pandas.DataFrame:
    """ユーザとタスクメタデータごとに、フェーズと状態別の値を集計する。

    Args:
        df_task: 履歴に基づく ``task_status_for_summary`` を含むタスク情報。
        metadata_keys: 集計対象のタスクメタデータキー。
        unit: 集計の単位。

    Returns:
        ユーザとタスクメタデータごとの集計結果を格納したDataFrame。
    """
    metadata_columns = [f"metadata.{key}" for key in metadata_keys or []]
    result_columns = ["account_id", *metadata_columns, *SUMMARY_COLUMNS]
    if len(df_task) == 0:
        return pandas.DataFrame(columns=result_columns)

    df = df_task.assign(account_id=df_task["account_id"].fillna(UNASSIGNED_ACCOUNT_ID))
    return summarize_df_task(df, group_columns=["account_id", *metadata_columns], unit=unit)


def create_legacy_task_count_summary_df(task_list: list[Task]) -> pandas.DataFrame:
    """非推奨コマンドと互換性のあるタスク数の集計結果を生成する。

    Args:
        task_list: タスク情報のリスト。

    Returns:
        従来形式で集計したDataFrame。
    """
    return create_task_count_summary_df(task_list)


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

    def create_summary_df(
        self,
        project_id: str,
        df_task: pandas.DataFrame,
        metadata_keys: list[str] | None = None,
        unit: AggregationUnit = AggregationUnit.TASK,
    ) -> pandas.DataFrame:
        """ユーザ情報を付与した集計結果を生成する。

        Args:
            project_id: プロジェクトID。
            df_task: 履歴に基づく状態を含むタスク情報。
            metadata_keys: 集計対象のタスクメタデータキー。
            unit: 集計の単位。

        Returns:
            ユーザ情報とフェーズ・状態別の集計結果を格納したDataFrame。
        """
        df_task_count = summarize_df_task_by_user(df_task, metadata_keys, unit)
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
        unit = AggregationUnit(args.unit)
        super().validate_project(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if args.legacy_output:
            self._main_legacy(project_id)
            return

        if unit in [AggregationUnit.VIDEO_DURATION_HOUR, AggregationUnit.VIDEO_DURATION_MINUTE]:
            project, _ = self.service.api.get_project(project_id)
            input_data_type = project["input_data_type"]
            if input_data_type != "movie":
                print(f"コマンドライン引数'--unit {unit.value}' は動画プロジェクトでのみ使用できます。現在のプロジェクトの入力データタイプは'{input_data_type}'です。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        def create_and_print_summary(temp_dir: Path) -> None:
            getting_obj = GettingTaskCountSummary(
                self.service,
                project_id,
                temp_dir,
                should_execute_get_tasks_api=args.execute_get_tasks_api,
                not_worked_threshold_second=args.not_worked_threshold_second,
                metadata_keys=args.metadata_key,
                unit=unit,
            )
            df_task = getting_obj.create_df_task()
            df = self.create_summary_df(project_id, df_task, args.metadata_key, unit)
            if len(df) == 0:
                logger.info("タスクが0件ですが、ヘッダ行を出力します。")
            self.print_summarize_df(df, args.metadata_key)

        if args.temp_dir is not None:
            create_and_print_summary(temp_dir=args.temp_dir)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                create_and_print_summary(temp_dir=Path(str_temp_dir))

    def _main_legacy(self, project_id: str) -> None:
        """非推奨コマンドと互換性のある処理を実行する。

        Args:
            project_id: プロジェクトID。

        Returns:
            None
        """
        args = self.args

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

            df = self.create_legacy_summary_df(project_id, task_list)
            if len(df) > 0:
                self.print_legacy_summarize_df(df)
            else:
                logger.error("出力対象データが0件のため、出力しません。")

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
        parser.add_argument(
            "--execute_get_tasks_api",
            action="store_true",
            help="タスク全件ファイルをダウンロードせずに、`getTasks` APIを実行してタスク一覧を取得します。"
            "`getTasks` APIを複数回実行するので、タスク全件ファイルをダウンロードするよりも時間がかかります。",
        )
        parser.add_argument(
            "--not_worked_threshold_second",
            type=float,
            default=0,
            help="作業していないとみなす作業時間の閾値を秒単位で指定します。この値以下の作業時間のタスクは、作業していないとみなします。",
        )
        parser.add_argument(
            "--unit",
            type=str,
            choices=[unit.value for unit in AggregationUnit],
            default=AggregationUnit.TASK.value,
            help="集計の単位を指定します。task_count: タスク数、input_data_count: 入力データ数、video_duration_hour: 動画の長さ（時間）、video_duration_minute: 動画の長さ（分）。",
        )
        parser.set_defaults(legacy_output=False)
    else:
        parser.set_defaults(metadata_key=None, execute_get_tasks_api=False, not_worked_threshold_second=0, unit=AggregationUnit.TASK.value, legacy_output=True)
        parser.add_argument(
            "--task_json",
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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskCountByUser(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_by_user"
    subcommand_help = "ユーザごとに、担当しているタスク数や入力データ数などを出力します。"
    description = "ユーザごとに、担当しているタスク数や入力データ数などをCSV形式で出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
