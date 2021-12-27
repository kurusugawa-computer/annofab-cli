import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, get_list_from_args
from annofabcli.common.utils import _catch_exception, print_csv, print_json
from annofabcli.stat_visualization.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.stat_visualization.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.stat_visualization.write_task_histogram import write_task_histogram
from annofabcli.stat_visualization.write_whole_linegraph import write_whole_linegraph
from annofabcli.statistics.csv import (
    FILENAME_PERFORMANCE_PER_DATE,
    FILENAME_PERFORMANCE_PER_FIRST_ANNOTATION_STARTED_DATE,
    FILENAME_PERFORMANCE_PER_USER,
    FILENAME_TASK_LIST,
)
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


def create_merged_performance_per_date(csv_path_list: List[Path]) -> WholeProductivityPerCompletedDate:
    """
    `日毎の生産量と生産性.csv` をマージしたDataFrameを返す。
    Args:
        csv_path_list:
    Returns:
    """
    df_list: List[pandas.DataFrame] = []
    for csv_path in csv_path_list:
        if csv_path.exists():
            df = pandas.read_csv(str(csv_path))
            df_list.append(df)
        else:
            logger.warning(f"{csv_path} は存在しませんでした。")
            continue

    if len(df_list) == 0:
        logger.warning(f"マージ対象のCSVファイルは存在しませんでした。")
        return pandas.DataFrame()

    sum_obj = WholeProductivityPerCompletedDate(df_list[0])
    for df in df_list[1:]:
        sum_obj = WholeProductivityPerCompletedDate.merge(sum_obj, WholeProductivityPerCompletedDate(df))

    return sum_obj


def merge_visualization_dir(  # pylint: disable=too-many-statements
    project_dir_list: List[Path],
    output_dir: Path,
    user_id_list: Optional[List[str]] = None,
    minimal_output: bool = False,
):
    @_catch_exception
    def execute_merge_performance_per_user():
        performance_per_user_csv_list = [dir / FILENAME_PERFORMANCE_PER_USER for dir in project_dir_list]

        obj_list = []
        for csv_file in performance_per_user_csv_list:
            if csv_file.exists():
                obj_list.append(UserPerformance.from_csv(csv_file))
            else:
                logger.warning(f"{csv_file} は存在しませんでした。")
                continue

        if len(obj_list) == 0:
            logger.warning(f"マージ対象のCSVファイルは存在しませんでした。")
            return

        sum_obj = obj_list[0]
        for obj in obj_list[1:]:
            sum_obj = UserPerformance.merge(sum_obj, obj)

        sum_obj.to_csv(output_dir / FILENAME_PERFORMANCE_PER_USER)

        whole_obj = WholePerformance(sum_obj.get_summary())
        whole_obj.to_csv(output_dir / "全体の生産性と品質.csv")

    @_catch_exception
    def execute_merge_performance_per_date():
        performance_per_date_csv_list = [dir / FILENAME_PERFORMANCE_PER_DATE for dir in project_dir_list]
        obj = create_merged_performance_per_date(performance_per_date_csv_list)
        obj.to_csv(output_dir / FILENAME_PERFORMANCE_PER_DATE)

    @_catch_exception
    def merge_performance_per_first_annotation_started_date():
        csv_list = [dir / FILENAME_PERFORMANCE_PER_FIRST_ANNOTATION_STARTED_DATE for dir in project_dir_list]
        df_list: List[pandas.DataFrame] = []
        for csv in csv_list:
            if csv.exists():
                df = pandas.read_csv(str(csv))
                df_list.append(df)
            else:
                logger.warning(f"{csv} は存在しませんでした。")
                continue

        if len(df_list) == 0:
            logger.warning(f"マージ対象のCSVファイルは存在しませんでした。")
            return

        sum_obj = WholeProductivityPerFirstAnnotationStartedDate(df_list[0])
        for df in df_list[1:]:
            sum_obj = WholeProductivityPerFirstAnnotationStartedDate.merge(
                sum_obj, WholeProductivityPerFirstAnnotationStartedDate(df)
            )

        sum_obj.to_csv(output_dir / FILENAME_PERFORMANCE_PER_FIRST_ANNOTATION_STARTED_DATE)

        sum_obj.plot(output_dir / "line-graph/折れ線-横軸_教師付開始日-全体.html")

    @_catch_exception
    def merge_worktime_per_date():
        csv_list = [dir / "ユーザ_日付list-作業時間.csv" for dir in project_dir_list]
        df_list: List[pandas.DataFrame] = []
        for csv in csv_list:
            if csv.exists():
                df = pandas.read_csv(str(csv))
                df_list.append(df)
            else:
                logger.warning(f"{csv} は存在しませんでした。")
                continue

        if len(df_list) == 0:
            logger.warning(f"マージ対象のCSVファイル 'ユーザ_日付list-作業時間.csv'は存在しませんでした。")
            return

        sum_obj = WorktimePerDate(df_list[0])
        for df in df_list[1:]:
            sum_obj = WorktimePerDate.merge(sum_obj, WorktimePerDate(df))

        sum_obj.to_csv(output_dir / "ユーザ_日付list-作業時間.csv")

        sum_obj.plot_cumulatively(output_dir / "line-graph/累積折れ線-横軸_日-縦軸_作業時間.html", user_id_list)

    @_catch_exception
    def merge_task_list() -> pandas.DataFrame:
        list_df = []
        for project_dir in project_dir_list:
            csv_path = project_dir / FILENAME_TASK_LIST
            if csv_path.exists():
                list_df.append(pandas.read_csv(str(csv_path)))
            else:
                logger.warning(f"{csv_path} は存在しませんでした。")
                continue

        df = pandas.concat(list_df, axis=0)
        return df

    @_catch_exception
    def write_info_json() -> None:
        info = {"target_dir_list": [str(e) for e in project_dir_list]}
        print_json(info, is_pretty=True, output=str(output_dir / "info.json"))

    execute_merge_performance_per_user()
    execute_merge_performance_per_date()
    merge_performance_per_first_annotation_started_date()
    merge_worktime_per_date()

    df_task = merge_task_list()
    print_csv(df_task, output=str(output_dir / FILENAME_TASK_LIST))

    # HTML生成
    write_performance_scatter_per_user(
        csv=output_dir / FILENAME_PERFORMANCE_PER_USER, output_dir=output_dir / "scatter"
    )
    write_whole_linegraph(csv=output_dir / FILENAME_PERFORMANCE_PER_DATE, output_dir=output_dir / "line-graph")

    write_linegraph_per_user(
        csv=output_dir / FILENAME_TASK_LIST,
        output_dir=output_dir / "line-graph",
        minimal_output=minimal_output,
        user_id_list=user_id_list,
    )

    write_task_histogram(csv=output_dir / FILENAME_TASK_LIST, output_dir=output_dir / "histogram")

    # info.jsonを出力
    write_info_json()


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
        output_dir=args.output_dir,
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
