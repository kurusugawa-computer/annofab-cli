import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, get_list_from_args
from annofabcli.common.utils import _catch_exception
from annofabcli.stat_visualization.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.stat_visualization.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.stat_visualization.write_whole_linegraph import write_whole_linegraph
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_DATE, FILENAME_PERFORMANCE_PER_USER
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.project_dir import MergingInfo, ProjectDir

logger = logging.getLogger(__name__)


def merge_visualization_dir(  # pylint: disable=too-many-statements
    project_dir_list: List[ProjectDir],
    output_project_dir: ProjectDir,
    user_id_list: Optional[List[str]] = None,
    minimal_output: bool = False,
):
    @_catch_exception
    def execute_merge_performance_per_user():
        merged_user_performance: Optional[UserPerformance] = None
        for project_dir in project_dir_list:
            try:
                user_performance = project_dir.read_user_performance()
            except Exception:
                logger.warning(f"'{project_dir}'のメンバごとの生産性と品質の取得に失敗しました。", exc_info=True)
                continue

            if merged_user_performance is None:
                merged_user_performance = user_performance
            else:
                merged_user_performance = UserPerformance.merge(merged_user_performance, user_performance)

        if merged_user_performance is not None:
            output_project_dir.write_user_performance(merged_user_performance)
            whole_performance = WholePerformance.from_user_performance(merged_user_performance)
            output_project_dir.write_whole_performance(whole_performance)

        else:
            logger.warning(
                f"マージ対象の'メンバごとの生産性と品質'は存在しないため、'{output_project_dir.FILENAME_USER_PERFORMANCE}', '{output_project_dir.FILENAME_WHOLE_PERFORMANCE}'は出力しません。"  # noqa: E501
            )

    @_catch_exception
    def execute_merge_performance_per_date():
        merged_obj: Optional[WholeProductivityPerCompletedDate] = None
        for project_dir in project_dir_list:
            try:
                tmp_obj = project_dir.read_whole_productivity_per_date()
            except Exception:
                logger.warning(f"'{project_dir}'の日ごとの生産量と生産性の取得に失敗しました。", exc_info=True)
                continue

            if merged_obj is None:
                merged_obj = tmp_obj
            else:
                merged_obj = WholeProductivityPerCompletedDate.merge(merged_obj, tmp_obj)

        if merged_obj is not None:
            output_project_dir.write_whole_productivity_per_date(merged_obj)

        else:
            logger.warning(
                f"マージ対象の'日ごとの生産量と生産性'は存在しないため、'{output_project_dir.FILENAME_WHOLE_PRODUCTIVITY_PER_DATE}'は出力しません。"
            )  # noqa: E501

    @_catch_exception
    def merge_performance_per_first_annotation_started_date():
        merged_obj: Optional[WholeProductivityPerFirstAnnotationStartedDate] = None
        for project_dir in project_dir_list:
            try:
                tmp_obj = project_dir.read_whole_productivity_per_first_annotation_started_date()
            except Exception:
                logger.warning(f"'{project_dir}'の教師付開始日ごとの生産量と生産性の取得に失敗しました。", exc_info=True)
                continue

            if merged_obj is None:
                merged_obj = tmp_obj
            else:
                merged_obj = WholeProductivityPerFirstAnnotationStartedDate.merge(merged_obj, tmp_obj)

        if merged_obj is not None:
            output_project_dir.write_whole_productivity_per_first_annotation_started_date(merged_obj)
            # TODO 見直す
            merged_obj.plot(output_project_dir.project_dir / "line-graph/折れ線-横軸_教師付開始日-全体.html")
        else:
            logger.warning(
                f"マージ対象の'教師付開始日ごとの生産量と生産性'は存在しないため、'{output_project_dir.FILENAME_WHOLE_PRODUCTIVITY_PER_FIRST_ANNOTATION_STARTED_DATE}'とそのCSVから生成される折れ線グラフは出力しません。"  # noqa: E501
            )

    @_catch_exception
    def merge_worktime_per_date():
        merged_obj: Optional[WorktimePerDate] = None
        for project_dir in project_dir_list:
            try:
                tmp_obj = project_dir.read_worktime_per_date_user()
            except Exception:
                logger.warning(f"'{project_dir}'からユーザごと日ごとの作業時間の取得に失敗しました。", exc_info=True)
                continue

            if merged_obj is None:
                merged_obj = tmp_obj
            else:
                merged_obj = WorktimePerDate.merge(merged_obj, tmp_obj)

        if merged_obj is not None:
            output_project_dir.write_worktime_per_date_user(merged_obj)
            # TODO 見直す
            merged_obj.plot_cumulatively(
                output_project_dir.project_dir / "line-graph/累積折れ線-横軸_日-縦軸_作業時間.html", user_id_list
            )
        else:
            logger.warning(
                f"マージ対象の'ユーザごと日ごとの作業時間'は存在しないため、'{output_project_dir.FILENAME_WORKTIME_PER_DATE_USER}'とそのCSVから生成される折れ線グラフは出力しません。"  # noqa: E501
            )

    @_catch_exception
    def merge_task_list() -> pandas.DataFrame:

        merged_obj: Optional[Task] = None
        for project_dir in project_dir_list:
            try:
                tmp_obj = project_dir.read_task_list()
            except Exception:
                logger.warning(f"'{project_dir}'からタスク情報の取得に失敗しました。", exc_info=True)
                continue

            if merged_obj is None:
                merged_obj = tmp_obj
            else:
                merged_obj = Task.merge(merged_obj, tmp_obj)

        if merged_obj is not None:
            output_project_dir.write_task_list(merged_obj)
            output_project_dir.write_task_histogram(merged_obj)

        else:
            logger.warning(
                f"マージ対象のタスク情報は存在しないため、'{output_project_dir.FILENAME_TASK_LIST}'とそのCSVから生成されるヒストグラム出力しません。"
            )  # noqa: E501

    @_catch_exception
    def write_merge_info_json() -> None:
        """マージ情報に関するJSONファイルを出力する。"""
        target_dir_list = [str(e.project_dir) for e in project_dir_list]
        project_info_list = []
        for project_dir in project_dir_list:
            try:
                project_info = project_dir.read_project_info()
                project_info_list.append(project_info)
            except Exception:
                logger.warning(f"'{project_dir}'からプロジェクト情報の取得に失敗しました。", exc_info=True)
                continue

        merge_info = MergingInfo(target_dir_list=target_dir_list, project_info_list=project_info_list)
        output_project_dir.write_merge_info(merge_info)

    execute_merge_performance_per_user()
    execute_merge_performance_per_date()
    merge_performance_per_first_annotation_started_date()
    merge_worktime_per_date()
    merge_task_list()
    # HTML生成
    write_performance_scatter_per_user(
        csv=output_project_dir.project_dir / FILENAME_PERFORMANCE_PER_USER,
        output_dir=output_project_dir.project_dir / "scatter",
    )
    write_whole_linegraph(
        csv=output_project_dir.project_dir / FILENAME_PERFORMANCE_PER_DATE,
        output_dir=output_project_dir.project_dir / "line-graph",
    )

    write_linegraph_per_user(
        csv=output_project_dir.project_dir / output_project_dir.FILENAME_TASK_LIST,
        output_dir=output_project_dir.project_dir / "line-graph",
        minimal_output=minimal_output,
        user_id_list=user_id_list,
    )

    # info.jsonを出力
    write_merge_info_json()


def validate(args: argparse.Namespace) -> bool:
    COMMON_MESSAGE = "annofabcli stat_visualization merge:"
    if len(args.dir) < 2:
        print(f"{COMMON_MESSAGE} argument --dir: マージ対象のディレクトリは2つ以上指定してください。", file=sys.stderr)
        return False

    return True


def main(args):
    if not validate(args):
        sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

    user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

    merge_visualization_dir(
        project_dir_list=args.dir,
        user_id_list=user_id_list,
        minimal_output=args.minimal,
        output_project_dir=ProjectDir(args.output_dir),
    )


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("--dir", type=Path, nargs="+", required=True, help="マージ対象ディレクトリ。2つ以上指定してください。")
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクト名のディレクトリが出力される。")

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "ユーザごとの折れ線グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人のユーザ情報がプロットされます。"
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "merge"
    subcommand_help = "``annofabcli statistics visualize`` コマンドの出力結果をマージします。"
    description = "``annofabcli statistics visualize`` コマンドの出力結果をマージします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
