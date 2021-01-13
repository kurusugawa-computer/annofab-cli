import argparse
import logging
from pathlib import Path

import annofabcli
from annofabcli.statistics.csv import write_summarise_whole_peformance_csv

logger = logging.getLogger(__name__)


def main(args):
    write_summarise_whole_peformance_csv(csv_path_list=args.csv, output_path=args.output)


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
