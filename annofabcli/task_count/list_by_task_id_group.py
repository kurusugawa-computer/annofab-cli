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
from annofabcli.task_count.common import SUMMARY_COLUMNS, summarize_df_task
from annofabcli.task_count.list_by_phase import AggregationUnit, GettingTaskCountSummary

logger = logging.getLogger(__name__)

TASK_ID_GROUP_UNKNOWN = "unknown"
"""task_id_groupが不明な場合に表示する値。"""

SINGLE_TASK_ID_GROUP_NAME = "all"
"""すべてのタスクを1グループとして集計するときのtask_id_group。"""


def positive_int(value: str) -> int:
    """文字列を1以上の整数に変換する。

    Args:
        value: コマンドライン引数で指定された値。

    Returns:
        変換後の整数。

    Raises:
        argparse.ArgumentTypeError: 1未満の値が指定された場合。
    """
    int_value = int(value)
    if int_value < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。")
    return int_value


def get_task_id_prefix(task_id: str, delimiter: str, component_count: int | None = None) -> str:
    """タスクIDから、末尾の区切り文字より前にあるプレフィックスを取得する。

    Args:
        task_id: タスクID。
        delimiter: プレフィックスと連番を分ける区切り文字。
        component_count: グループ名として使用する先頭要素の数。未指定の場合は末尾の1要素を除く。

    Returns:
        タスクIDのプレフィックス。区切り文字が存在しない場合は ``unknown``。
    """
    elements = task_id.split(delimiter)
    if component_count is None:
        component_count = len(elements) - 1
    if component_count < 1 or len(elements) < component_count:
        return TASK_ID_GROUP_UNKNOWN
    return delimiter.join(elements[:component_count])


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
    task_id_group_component_count: int | None = None,
    is_single_group: bool = False,
    unit: AggregationUnit = AggregationUnit.TASK,
) -> pandas.DataFrame:
    """タスクIDグループごとに、フェーズと状態別のタスク数を集計する。

    Args:
        df_task: ``task_id``、``phase``、``task_status_for_summary`` 列を持つDataFrame。
        task_id_delimiter: タスクIDからグループを取得するための区切り文字。
        task_id_groups: タスクIDグループをキー、タスクIDのリストを値とする辞書。
        task_id_group_component_count: グループ名として使用する、タスクIDの先頭要素の数。
        is_single_group: すべてのタスクを1グループとして集計するかどうか。
        unit: 集計の単位。

    Returns:
        タスクIDグループごとのタスク数を横持ちで格納したDataFrame。
    """
    if len(df_task) == 0:
        return pandas.DataFrame(columns=["task_id_group", *SUMMARY_COLUMNS])

    if is_single_group:
        df = df_task.assign(task_id_group=SINGLE_TASK_ID_GROUP_NAME)
    elif task_id_groups is not None:
        df_task_id_group = _create_task_id_group_df(task_id_groups)
        df = df_task.merge(df_task_id_group, on="task_id", how="left")
        df["task_id_group"] = df["task_id_group"].fillna(TASK_ID_GROUP_UNKNOWN)
    else:
        if task_id_delimiter is None:
            raise ValueError("task_id_delimiterまたはtask_id_groupsのどちらかを指定してください。")
        df = df_task.assign(task_id_group=df_task["task_id"].map(lambda task_id: get_task_id_prefix(task_id, task_id_delimiter, task_id_group_component_count)))

    return summarize_df_task(df, group_columns=["task_id_group"], unit=unit)


class ListTaskCountByTaskIdGroup(CommandLine):
    """タスクIDグループごとのタスク数をCSV形式で出力する。"""

    def list_task_count_by_task_id_group(
        self,
        project_id: str,
        *,
        task_id_delimiter: str | None,
        task_id_groups: dict[str, list[str]] | None,
        task_id_group_component_count: int | None,
        is_single_group: bool,
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
            task_id_group_component_count: グループ名として使用する、タスクIDの先頭要素の数。
            is_single_group: すべてのタスクを1グループとして集計するかどうか。
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
            task_id_group_component_count=task_id_group_component_count,
            is_single_group=is_single_group,
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
                task_id_group_component_count=args.task_id_group_component_count,
                is_single_group=args.single_group,
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
                    task_id_group_component_count=args.task_id_group_component_count,
                    is_single_group=args.single_group,
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
    task_id_group.add_argument(
        "--single_group",
        action="store_true",
        help="すべてのタスクを ``all`` という1つのタスクIDグループとして集計します。",
    )
    parser.add_argument(
        "--task_id_group_component_count",
        type=positive_int,
        help="タスクIDを ``--task_id_delimiter`` で分割し、先頭から何要素をグループ名として使用するか指定します。``--task_id_delimiter`` と一緒に指定してください。",
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
    parser.set_defaults(command_parser=parser)
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """コマンドライン引数からコマンドを実行する。

    Args:
        args: コマンドライン引数。

    Returns:
        None
    """
    if args.task_id_group_component_count is not None and args.task_id_delimiter is None:
        args.command_parser.error("--task_id_group_component_countは--task_id_delimiterと一緒に指定してください。")

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
