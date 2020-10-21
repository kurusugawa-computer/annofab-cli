import argparse
import logging
from pathlib import Path
from typing import List, Optional, Set

import pandas

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.common.utils import print_csv, print_json
from annofabcli.experimental.mask_user_info import create_masked_user_info_df
from annofabcli.experimental.merge_peformance_per_date import merge_peformance_per_date
from annofabcli.experimental.merge_peformance_per_user import merge_peformance_per_user
from annofabcli.experimental.write_linegraph_per_user import write_linegraph_per_user
from annofabcli.experimental.write_performance_scatter_per_user import write_performance_scatter_per_user
from annofabcli.experimental.write_task_histogram import write_task_histogram
from annofabcli.experimental.write_whole_linegraph import write_whole_linegraph
from annofabcli.statistics.csv import Csv

logger = logging.getLogger(__name__)


FILENAME_PEFORMANCE_PER_USER = "メンバごとの生産性と品質.csv"
FILENAME_PEFORMANCE_PER_DATE = "日毎の生産量と生産性.csv"
FILENAME_TASK_LIST = "タスクlist.csv"


def merge_visualization(
    project_dir_list: List[Path],
    output_dir: Path,
    user_id_list: Optional[List[str]] = None,
    minimal_output: bool = False,
):
    def execute_merge_peformance_per_user():
        performance_per_user_csv_list = [dir / FILENAME_PEFORMANCE_PER_USER for dir in project_dir_list]
        merge_peformance_per_user(
            csv_path_list=performance_per_user_csv_list, output_path=output_dir / FILENAME_PEFORMANCE_PER_USER
        )

    def execute_merge_peformance_per_date():
        performance_per_date_csv_list = [dir / FILENAME_PEFORMANCE_PER_DATE for dir in project_dir_list]
        merge_peformance_per_date(
            csv_path_list=performance_per_date_csv_list, output_path=output_dir / FILENAME_PEFORMANCE_PER_DATE
        )

    def merge_task_list() -> pandas.DataFrame:
        list_df = [pandas.read_csv(str(dir / FILENAME_TASK_LIST)) for dir in project_dir_list]
        df = pandas.concat(list_df, axis=0)
        return df

    def write_csv_for_summary(df_task: pandas.DataFrame) -> None:
        """
        タスク関係のCSVを出力する。
        """
        csv_obj = Csv(str(output_dir))
        csv_obj.write_task_count_summary(df_task)
        csv_obj.write_worktime_summary(df_task)
        csv_obj.write_count_summary(df_task)

    def write_info_json() -> None:
        info = {"target_dir_list": [str(e) for e in project_dir_list]}
        print_json(info, is_pretty=True, output=str(output_dir / "info.json"))

    # CSV生成
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


def _get_member_perfomance_csv(project_dir: Path) -> Path:
    return f"{str(project_dir)}/メンバごとの生産性と品質.csv"


def _get_task_csv(project_dir: Path) -> str:
    return f"{str(project_dir)}/タスクlist.csv"


def _get_not_masked_user_id(
    df: pandas.DataFrame,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
) -> List[str]:
    df[("biography", "")].isin(not_masked_biography_set)


def mask_visualization_dir(
    project_dir: Path,
    output_dir: Path,
    not_masked_biography_set: Optional[Set[str]] = None,
    not_masked_user_id_set: Optional[Set[str]] = None,
):
    MEMBER_PERFOMANCE_CSV = "メンバごとの生産性と品質.csv"
    df_member_perfomance_csv = create_masked_user_info_df(
        csv=project_dir / MEMBER_PERFOMANCE_CSV,
        csv_header=2,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
    )
    print_csv(df_member_perfomance_csv, output=str(output_dir / MEMBER_PERFOMANCE_CSV))

    write_performance_scatter_per_user(output_dir / MEMBER_PERFOMANCE_CSV, output_dir=output_dir / "scatter")

    write_linegraph_per_user(output_dir / MEMBER_PERFOMANCE_CSV, output_dir=output_dir / "scatter")


def main(args):
    not_masked_biography_set = (
        set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    )
    not_masked_user_id_set = (
        set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
    )

    mask_visualization_dir(
        project_dir=args.dir,
        not_masked_biography_set=not_masked_biography_set,
        not_masked_user_id_set=not_masked_user_id_set,
        output_dir=args.output_dir,
    )
    #
    #
    # def main(self):
    #     args = self.args
    #
    #     not_masked_biography_set = (
    #         set(get_list_from_args(args.not_masked_biography)) if args.not_masked_biography is not None else None
    #     )
    #     not_masked_user_id_set = (
    #         set(get_list_from_args(args.not_masked_user_id)) if args.not_masked_user_id is not None else None
    #     )
    #
    #     df = create_masked_user_info_df(
    #         csv=args.csv,
    #         csv_header=args.csv_header,
    #         not_masked_biography_set=not_masked_biography_set,
    #         not_masked_user_id_set=not_masked_user_id_set,
    #     )
    #     self.print_csv(df)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--dir", type=Path, required=True, help="マスク対象のディレクトリ。`annofabcli statistics visualize`コマンドの出力結果。"
    )

    parser.add_argument(
        "--not_masked_biography",
        type=str,
        nargs="+",
        help="マスクしないユーザの`biography`を指定してください。",
    )

    parser.add_argument(
        "--not_masked_user_id",
        type=str,
        nargs="+",
        help="マスクしないユーザの`user_id`を指定してください。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "mask_visualization_dir"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力結果のユーザ情報をマスクします。"
    description = "`annofabcli statistics visualize`コマンドの出力結果のユーザ情報をマスクします。マスク対象のファイルのみ出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
