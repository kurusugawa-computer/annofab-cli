import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.common.utils import print_csv, print_json
from annofabcli.experimental.merge_peformance_per_date import create_df_merged_peformance_per_date
from annofabcli.experimental.merge_peformance_per_user import create_df_merged_peformance_per_user
from annofabcli.experimental.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.experimental.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.experimental.write_task_histogram import write_task_histogram
from annofabcli.experimental.write_whole_linegraph import write_whole_linegraph
from annofabcli.statistics.csv import (
    FILENAME_PEFORMANCE_PER_DATE,
    FILENAME_PEFORMANCE_PER_USER,
    FILENAME_TASK_LIST,
    Csv,
)

logger = logging.getLogger(__name__)


def merge_visualization_dir(
    project_dir_list: List[Path],
    output_dir: Path,
    user_id_list: Optional[List[str]] = None,
    minimal_output: bool = False,
):
    def execute_merge_peformance_per_user():
        performance_per_user_csv_list = [dir / FILENAME_PEFORMANCE_PER_USER for dir in project_dir_list]
        df_per_user = create_df_merged_peformance_per_user(csv_path_list=performance_per_user_csv_list)
        csv_obj.write_productivity_per_user(df_per_user)
        csv_obj.write_whole_productivity(df_per_user)

    def execute_merge_peformance_per_date():
        performance_per_date_csv_list = [dir / FILENAME_PEFORMANCE_PER_DATE for dir in project_dir_list]
        df_per_date = create_df_merged_peformance_per_date(performance_per_date_csv_list)
        csv_obj.write_whole_productivity_per_date(df_per_date)

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

    def write_csv_for_summary(df_task: pandas.DataFrame) -> None:
        """
        タスク関係のCSVを出力する。
        """
        csv_obj.write_task_count_summary(df_task)
        csv_obj.write_worktime_summary(df_task)
        csv_obj.write_count_summary(df_task)

    def write_info_json() -> None:
        info = {"target_dir_list": [str(e) for e in project_dir_list]}
        print_json(info, is_pretty=True, output=str(output_dir / "info.json"))

    # CSV生成
    csv_obj = Csv(str(output_dir))

    execute_merge_peformance_per_user()
    execute_merge_peformance_per_date()
    df_task = merge_task_list()
    print_csv(df_task, output=str(output_dir / FILENAME_TASK_LIST))
    write_csv_for_summary(df_task)

    # HTML生成
    write_performance_scatter_per_user(csv=output_dir / FILENAME_PEFORMANCE_PER_USER, output_dir=output_dir / "scatter")
    write_whole_linegraph(csv=output_dir / FILENAME_PEFORMANCE_PER_DATE, output_dir=output_dir / "line-graph")
    write_linegraph_per_user(
        csv=output_dir / FILENAME_TASK_LIST,
        output_dir=output_dir / "line-graph",
        minimal_output=minimal_output,
        user_id_list=user_id_list,
    )
    write_task_histogram(
        csv=output_dir / FILENAME_TASK_LIST, output_dir=output_dir / "histogram", minimal_output=minimal_output
    )

    # info.jsonを出力
    write_info_json()


def main(args):
    user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
    merge_visualization_dir(
        project_dir_list=args.dir,
        user_id_list=user_id_list,
        minimal_output=args.minimal,
        output_dir=args.output_dir,
    )


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("--dir", type=Path, nargs="+", required=True, help="マージ対象ディレクトリ")
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクト名のディレクトリが出力される。")

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "ユーザごとの折れ線グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人のユーザ情報がプロットされます。"
            "file://`を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "merge_visualization_dir"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力結果をマージします。"
    description = "`annofabcli statistics visualize`コマンドの出力結果をマージします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
