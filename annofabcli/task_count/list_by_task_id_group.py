from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.task_count.list_by_phase import AggregationUnit, GettingTaskCountSummary, TaskStatusForSummary

logger = logging.getLogger(__name__)

TASK_ID_GROUP_UNKNOWN = "unknown"
"""task_id_groupが不明な場合に表示する値。"""

SUMMARY_COLUMNS = [
    "annotation.never_worked",
    "annotation.worked",
    "annotation.on_hold",
    "inspection.never_worked",
    "inspection.worked",
    "inspection.on_hold",
    "acceptance.never_worked",
    "acceptance.worked",
    "acceptance.on_hold",
    "acceptance.complete",
]
"""タスクIDグループごとの集計結果に含める列。"""


def get_task_id_prefix(task_id: str, delimiter: str) -> str:
    """タスクIDから、末尾の区切り文字より前にあるプレフィックスを取得する。

    Args:
        task_id: タスクID。
        delimiter: プレフィックスと連番を分ける区切り文字。

    Returns:
        タスクIDのプレフィックス。区切り文字が存在しない場合は ``unknown``。
    """
    elements = task_id.split(delimiter)
    if len(elements) <= 1:
        return TASK_ID_GROUP_UNKNOWN
    return delimiter.join(elements[:-1])


def _get_summary_status(task_status_for_summary: str) -> str:
    """詳細なタスク状態を集計用の状態に変換する。

    Args:
        task_status_for_summary: ``task_count list_by_phase`` で使用するタスク状態。

    Returns:
        ``never_worked``、``worked``、``on_hold``、``complete`` のいずれか。
    """
    if task_status_for_summary in {
        TaskStatusForSummary.NEVER_WORKED_UNASSIGNED.value,
        TaskStatusForSummary.NEVER_WORKED_ASSIGNED.value,
    }:
        return "never_worked"
    if task_status_for_summary in {
        TaskStatusForSummary.WORKED_NOT_REJECTED.value,
        TaskStatusForSummary.WORKED_REJECTED.value,
    }:
        return "worked"
    return task_status_for_summary


def _create_task_id_group_df(task_id_groups: dict[str, list[str]]) -> pandas.DataFrame:
    """タスクIDとタスクIDグループとの対応を表すDataFrameを生成する。

    Args:
        task_id_groups: タスクIDグループをキー、タスクIDのリストを値とする辞書。

    Returns:
        ``task_id`` 列と ``task_id_group`` 列を持つDataFrame。
    """
    records = [{"task_id": task_id, "task_id_group": task_id_group} for task_id_group, task_id_list in task_id_groups.items() for task_id in task_id_list]
    return pandas.DataFrame(records, columns=["task_id", "task_id_group"])


def summarize_df_task_by_task_id_group(
    df_task: pandas.DataFrame,
    *,
    task_id_delimiter: str | None,
    task_id_groups: dict[str, list[str]] | None,
    unit: AggregationUnit = AggregationUnit.TASK,
) -> pandas.DataFrame:
    """タスクIDグループごとに、フェーズと状態別のタスク数を集計する。

    Args:
        df_task: ``task_id``、``phase``、``task_status_for_summary`` 列を持つDataFrame。
        task_id_delimiter: タスクIDからグループを取得するための区切り文字。
        task_id_groups: タスクIDグループをキー、タスクIDのリストを値とする辞書。
        unit: 集計の単位。

    Returns:
        タスクIDグループごとのタスク数を横持ちで格納したDataFrame。
    """
    result_columns = ["task_id_group", *SUMMARY_COLUMNS, "total"]
    if len(df_task) == 0:
        return pandas.DataFrame(columns=result_columns)

    if task_id_groups is not None:
        df_task_id_group = _create_task_id_group_df(task_id_groups)
        df = df_task.merge(df_task_id_group, on="task_id", how="left")
        df["task_id_group"] = df["task_id_group"].fillna(TASK_ID_GROUP_UNKNOWN)
    else:
        if task_id_delimiter is None:
            raise ValueError("task_id_delimiterまたはtask_id_groupsのどちらかを指定してください。")
        df = df_task.assign(task_id_group=df_task["task_id"].map(lambda task_id: get_task_id_prefix(task_id, task_id_delimiter)))

    summary_status = df["task_status_for_summary"].map(_get_summary_status)
    summary_phase = df["phase"].mask(summary_status == TaskStatusForSummary.COMPLETE.value, "acceptance")
    df = df.assign(summary_column=summary_phase + "." + summary_status)

    match unit:
        case AggregationUnit.TASK:
            df = df.assign(_aggregate_value=1)
        case AggregationUnit.INPUT_DATA:
            df = df.assign(_aggregate_value=df["input_data_count"])
        case AggregationUnit.VIDEO_DURATION_HOUR:
            df = df.assign(_aggregate_value=df["video_duration_hour"])
        case AggregationUnit.VIDEO_DURATION_MINUTE:
            df = df.assign(_aggregate_value=df["video_duration_minute"])

    df_summary = df.pivot_table(
        values="_aggregate_value",
        index="task_id_group",
        columns="summary_column",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    for column in SUMMARY_COLUMNS:
        if column not in df_summary.columns:
            df_summary[column] = 0

    df_summary["total"] = df_summary[SUMMARY_COLUMNS].sum(axis="columns")
    return df_summary[result_columns].sort_values("task_id_group").reset_index(drop=True)


class ListTaskCountByTaskIdGroup(CommandLine):
    """タスクIDグループごとのタスク数をCSV形式で出力する。"""

    def list_task_count_by_task_id_group(
        self,
        project_id: str,
        *,
        task_id_delimiter: str | None,
        task_id_groups: dict[str, list[str]] | None,
        temp_dir: Path,
        should_execute_get_tasks_api: bool = False,
        not_worked_threshold_second: float = 0,
        unit: AggregationUnit = AggregationUnit.TASK,
    ) -> None:
        """タスクIDグループごとのタスク数をCSV形式で出力する。

        Args:
            project_id: プロジェクトID。
            task_id_delimiter: タスクIDからグループを取得するための区切り文字。
            task_id_groups: タスクIDグループをキー、タスクIDのリストを値とする辞書。
            temp_dir: 一時ファイルの保存先ディレクトリ。
            should_execute_get_tasks_api: getTasks APIを実行するかどうか。
            not_worked_threshold_second: 作業していないとみなす作業時間の閾値（秒）。
            unit: 集計の単位。

        Returns:
            None
        """
        logger.info(f"project_id='{project_id}' :: タスクIDグループごとの'{unit.value}'を集計します。")
        getting_obj = GettingTaskCountSummary(
            self.service,
            project_id,
            temp_dir,
            should_execute_get_tasks_api=should_execute_get_tasks_api,
            not_worked_threshold_second=not_worked_threshold_second,
            unit=unit,
        )
        df_task = getting_obj.create_df_task()
        df_summary = summarize_df_task_by_task_id_group(
            df_task,
            task_id_delimiter=task_id_delimiter,
            task_id_groups=task_id_groups,
            unit=unit,
        )
        if len(df_task) == 0:
            logger.info("タスクが0件ですが、ヘッダ行を出力します。")
        else:
            logger.info(f"{len(df_task)} 件のタスクを集計しました。")
        self.print_csv(df_summary)
        logger.info(f"project_id='{project_id}' :: タスクIDグループごとの'{unit.value}'をCSV形式で出力しました。")

    def main(self) -> None:
        """コマンドを実行する。

        Returns:
            None
        """
        args = self.args
        project_id = args.project_id
        unit = AggregationUnit(args.unit)
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        if unit in [AggregationUnit.VIDEO_DURATION_HOUR, AggregationUnit.VIDEO_DURATION_MINUTE]:
            project, _ = self.service.api.get_project(project_id)
            input_data_type = project["input_data_type"]
            if input_data_type != "movie":
                print(f"コマンドライン引数'--unit {unit.value}' は動画プロジェクトでのみ使用できます。現在のプロジェクトの入力データタイプは'{input_data_type}'です。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        task_id_groups = get_json_from_args(args.task_id_groups)
        if args.temp_dir is not None:
            self.list_task_count_by_task_id_group(
                project_id,
                task_id_delimiter=args.task_id_delimiter,
                task_id_groups=task_id_groups,
                temp_dir=args.temp_dir,
                should_execute_get_tasks_api=args.execute_get_tasks_api,
                not_worked_threshold_second=args.not_worked_threshold_second,
                unit=unit,
            )
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                self.list_task_count_by_task_id_group(
                    project_id,
                    task_id_delimiter=args.task_id_delimiter,
                    task_id_groups=task_id_groups,
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

    task_id_group = parser.add_mutually_exclusive_group(required=True)
    task_id_group.add_argument(
        "--task_id_delimiter",
        type=str,
        help="タスクIDのプレフィックスと連番を分ける区切り文字を指定します。たとえば ``_`` を指定すると、タスクID ``aa_bb_001`` のグループは ``aa_bb`` になります。",
    )
    task_id_group.add_argument(
        "--task_id_groups",
        type=str,
        help="タスクIDグループをキー、タスクIDのリストを値とするJSON文字列を指定します。``file://`` を先頭に付けるとJSONファイルを指定できます。",
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
    ListTaskCountByTaskIdGroup(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """サブコマンドのパーサーを追加する。

    Args:
        subparsers: サブパーサー。

    Returns:
        追加した引数パーサー。
    """
    subcommand_name = "list_by_task_id_group"
    subcommand_help = "タスクIDのグループごとに、フェーズと状態別のタスク数をCSV形式で出力します。"
    epilog = "オーナロールまたはアノテーションユーザーロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
