import argparse
import logging
from pathlib import Path
from typing import List

import pandas

import annofabcli
from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


def read_whole_peformance_csv(csv_path: Path) -> pandas.Series:
    """
    '全体の生産量と生産性.csv' を読み込む。
    プロジェクト名はディレクトリ名とする。
    """
    project_title = csv_path.parent.name
    if csv_path.exists():
        df = pandas.read_csv(str(csv_path), header=None, index_col=[0, 1])
        series = df[2]
        series[("project_title", "")] = project_title
    else:
        logger.warning(f"{csv_path} は存在しませんでした。")
        series = pandas.Series([project_title], index=pandas.MultiIndex.from_tuples([("project_title", "")]))

    return series


def summarise_whole_peformance_csv(csv_path_list: List[Path]) -> pandas.DataFrame:
    series_list = [read_whole_peformance_csv(csv_path) for csv_path in csv_path_list]
    df = pandas.DataFrame(series_list)

    first_column = ("project_title", "")
    tmp_columns = list(df.columns)
    tmp_columns.remove(first_column)
    df = df[[first_column] + tmp_columns]
    return df


def main(args):
    output_path: Path = args.output
    df = summarise_whole_peformance_csv(csv_path_list=args.csv)
    print_csv(df, str(output_path))


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=(
            "CSVファイルのパスを複数指定してください。"
            "CSVは、`annofabcli statistics visualize`コマンドの出力ファイルである複数の'全体の生産量と生産性.csv'と同じフォーマットです。"
        ),
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarise_whole_peformance_csv"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力ファイルである複数の'全体の生産量と生産性.csv'の値をプロジェクトごとにまとめます。"
    description = "`annofabcli statistics visualize`コマンドの出力ファイルである複数の'全体の生産量と生産性.csv'の値をプロジェクトごとにまとめます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
