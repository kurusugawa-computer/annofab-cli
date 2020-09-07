import argparse
import logging
import os
import subprocess
from argparse import ArgumentParser
from pathlib import Path
from typing import List

import pandas
import annofabcli

from annofabcli.experimental.merge_peformance_per_date import merge_peformance_per_date
from annofabcli.experimental.merge_peformance_per_user import merge_peformance_per_user
from annofabcli.experimental.write_linegraph_per_user import write_linegraph_by_user
from annofabcli.experimental.write_performance_scatter_per_user import write_performance_scatter_per_user


from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


FILENAME_PEFORMANCE_PER_USER = "メンバごとの生産性と品質.csv"
FILENAME_PEFORMANCE_PER_DATE = "日毎の生産量と生産性.csv"
FILENAME_TASK_LIST = "タスクlist.csv"


def merge_visualization(
    project_dir_list: List[Path],
    output_dir: Path,
):
    def execute_merge_peformance_per_user():
        performance_per_user_csv_list = [str(dir / FILENAME_PEFORMANCE_PER_USER) for dir in project_dir_list]
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "merge_peformance_per_user",
            "--output",
            str(output_dir / FILENAME_PEFORMANCE_PER_USER),
            "--csv",
        ] + performance_per_user_csv_list
        subprocess.run(command_args, check=True)

    def execute_merge_peformance_per_date():
        performance_per_date_csv_list = [str(dir / FILENAME_PEFORMANCE_PER_DATE) for dir in project_dir_list]
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "merge_peformance_per_date",
            "--output",
            str(output_dir / FILENAME_PEFORMANCE_PER_DATE),
            "--csv",
        ] + performance_per_date_csv_list
        subprocess.run(command_args, check=True)

    def merge_task_list():
        list_df = [pandas.read_csv(str(dir / FILENAME_TASK_LIST)) for dir in project_dir_list]
        df = pandas.concat(list_df, axis=0)
        print_csv(df)

    def write_performance_scatter_per_user():
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "write_performance_scatter_per_user",
            "--minimal",
            "--csv",
            str(output_dir / FILENAME_PEFORMANCE_PER_USER),
            "--output_dir",
            str(output_dir / "scatter"),
        ]
        subprocess.run(command_args, check=True)

    def write_whole_linegraph():
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "write_whole_linegraph",
            "--csv",
            str(output_dir / FILENAME_PEFORMANCE_PER_DATE),
            "--output_dir",
            str(output_dir / "line-graph"),
        ]
        subprocess.run(command_args, check=True)

    def write_linegraph_per_user():
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "write_linegraph_per_user",
            "--minimal",
            "--csv",
            str(output_dir / FILENAME_TASK_LIST),
            "--output_dir",
            str(output_dir / "line-graph"),
        ]
        subprocess.run(command_args, check=True)

    def write_task_histogram():
        command_args = [
            "poetry",
            "run",
            "annofabcli",
            "experimental",
            "write_task_histogram",
            "--minimal",
            "--csv",
            str(output_dir / FILENAME_TASK_LIST),
            "--output_dir",
            str(output_dir / "histogram"),
        ]
        subprocess.run(command_args, check=True)

    # ディレクトリ移動
    now_dir = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../../")

    # CSV生成
    execute_merge_peformance_per_user()
    execute_merge_peformance_per_date()
    merge_task_list()

    # HTML生成
    write_performance_scatter_per_user()
    write_whole_linegraph()
    write_linegraph_per_user()
    write_task_histogram()

    # 移動前のディレクトリに戻る
    os.chdir(now_dir)

def main(args):
    merge_visualization(
        project_dir_list=args.dir,
        output_dir=args.output_dir,
    )


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("--dir", type=Path, nargs="+", required=True, help="マージ対象ディレクトリ")
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクト名のディレクトリが出力される。")
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "merge_visualization_dir"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力結果をマージする。"
    description = "`annofabcli statistics visualize`コマンドの出力結果をマージする。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
