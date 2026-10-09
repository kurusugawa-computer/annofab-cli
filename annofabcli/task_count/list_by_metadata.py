"""タスクメタデータごとに、フェーズと状態別の値を集計するコマンド。"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_count.common import summarize_df_task
from annofabcli.task_count.list_by_phase import AggregationUnit, GettingTaskCountSummary
from annofabcli.task_count.output import print_task_count_summary

logger = logging.getLogger(__name__)


def summarize_df_task_by_metadata(
    df_task: pandas.DataFrame,
    *,
    metadata_keys: list[str],
    unit: AggregationUnit = AggregationUnit.TASK,
) -> pandas.DataFrame:
    """タスクメタデータごとに、フェーズと状態別の値を集計する。

    Args:
        df_task: タスク情報を格納したDataFrame。
        metadata_keys: 集計対象のタスクメタデータキー。
        unit: 集計の単位。

    Returns:
        タスクメタデータごとの集計結果を格納したDataFrame。
    """
    metadata_columns = [f"metadata.{key}" for key in metadata_keys]
    return summarize_df_task(df_task, group_columns=metadata_columns, unit=unit)


class ListTaskCountByMetadata(CommandLine):
    """タスクメタデータごとの値を指定した形式で出力する。"""

    def list_task_count_by_metadata(
        self,
        project_id: str,
        *,
        metadata_keys: list[str],
        temp_dir: Path,
        should_execute_get_tasks_api: bool = False,
        not_worked_threshold_second: float = 0,
        unit: AggregationUnit = AggregationUnit.TASK,
    ) -> None:
        """タスクメタデータごとの値を指定した形式で出力する。

        Args:
            project_id: プロジェクトID。
            metadata_keys: 集計対象のタスクメタデータキー。
            temp_dir: 一時ファイルの保存先ディレクトリ。
            should_execute_get_tasks_api: getTasks APIを実行するかどうか。
            not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）。
            unit: 集計の単位。

        Returns:
            None
        """
        logger.info(f"project_id='{project_id}' :: タスクメタデータごとの'{unit.value}'を集計します。")
        getting_obj = GettingTaskCountSummary(
            self.service,
            project_id,
            temp_dir,
            should_execute_get_tasks_api=should_execute_get_tasks_api,
            not_worked_threshold_second=not_worked_threshold_second,
            metadata_keys=metadata_keys,
            unit=unit,
        )
        df_task = getting_obj.create_df_task()
        df_summary = summarize_df_task_by_metadata(df_task, metadata_keys=metadata_keys, unit=unit)
        if len(df_task) == 0:
            logger.info("タスクが0件のため、空の集計結果を出力します。")
        else:
            logger.info(f"{len(df_task)} 件のタスクを集計しました。")
        print_task_count_summary(df_summary, format=OutputFormat(self.str_format), output=self.output)
        logger.info(f"project_id='{project_id}' :: タスクメタデータごとの'{unit.value}'を指定した形式で出力しました。")

    def main(self) -> None:
        """コマンドを実行する。

        Returns:
            None
        """
        args = self.args
        project_id = args.project_id
        unit = AggregationUnit(args.unit)
        super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if unit in [AggregationUnit.VIDEO_DURATION_HOUR, AggregationUnit.VIDEO_DURATION_MINUTE]:
            project, _ = self.service.api.get_project(project_id)
            input_data_type = project["input_data_type"]
            if input_data_type != "movie":
                print(f"コマンドライン引数'--unit {unit.value}' は動画プロジェクトでのみ使用できます。現在のプロジェクトの入力データタイプは'{input_data_type}'です。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        if args.temp_dir is not None:
            self.list_task_count_by_metadata(
                project_id,
                metadata_keys=args.metadata_key,
                temp_dir=args.temp_dir,
                should_execute_get_tasks_api=args.execute_get_tasks_api,
                not_worked_threshold_second=args.not_worked_threshold_second,
                unit=unit,
            )
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                self.list_task_count_by_metadata(
                    project_id,
                    metadata_keys=args.metadata_key,
                    temp_dir=Path(str_temp_dir),
                    should_execute_get_tasks_api=args.execute_get_tasks_api,
                    not_worked_threshold_second=args.not_worked_threshold_second,
                    unit=unit,
                )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を定義する。

    Args:
        parser: 引数パーサー。

    Returns:
        None
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    parser.add_argument(
        "--metadata_key",
        type=str,
        nargs="+",
        required=True,
        help="集計対象のタスクメタデータキーを指定します。複数指定した場合は、指定したキーの値の組み合わせで集計します。",
    )
    parser.add_argument(
        "--execute_get_tasks_api",
        action="store_true",
        help="タスク全件ファイルをダウンロードせずに、`getTasks` APIを実行してタスク一覧を取得します。`getTasks` APIを複数回実行するので、タスク全件ファイルをダウンロードするよりも時間がかかります。",
    )
    parser.add_argument(
        "--not_worked_threshold_second",
        type=float,
        default=0,
        help="作業していないとみなす作業時間の閾値を秒単位で指定します。この値以下の作業時間のタスクは、作業していないとみなします。",
    )
    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、一時ファイルをダウンロードします。",
    )
    parser.add_argument(
        "--unit",
        type=str,
        choices=[unit.value for unit in AggregationUnit],
        default=AggregationUnit.TASK.value,
        help="集計の単位を指定します。task_count: タスク数、input_data_count: 入力データ数、video_duration_hour: 動画の長さ（時間）、video_duration_minute: 動画の長さ（分）。",
    )
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """コマンドライン引数からコマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListTaskCountByMetadata(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """サブコマンドのパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_name = "list_by_metadata"
    subcommand_help = "タスクメタデータごとに、フェーズと状態別のタスク数などを指定した形式で出力します。"
    epilog = "オーナロールまたはアノテーションユーザーロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
