import argparse
import logging
from pathlib import Path

import annofabcli
from annofabcli.statistics.csv import FILENAME_WHOLE_PEFORMANCE, write_summarise_whole_peformance_csv

logger = logging.getLogger(__name__)


def main(args):
    root_dir: Path = args.dir
    csv_path_list = [
        project_dir / FILENAME_WHOLE_PEFORMANCE
        for project_dir in root_dir.iterdir()
        if (project_dir / FILENAME_WHOLE_PEFORMANCE).exists()
    ]
    write_summarise_whole_peformance_csv(csv_path_list=csv_path_list, output_path=args.output)


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="プロジェクトディレクトリが存在するディレクトリを指定してください。プロジェクトディレクトリ内の`全体の生産性と品質.csv`というファイルを読み込みます。",
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarise_whole_peformance_csv"
    subcommand_help = "`annofabcli statistics visualize`コマンドの出力ファイルである複数の'全体の生産性と品質.csv'の値をプロジェクトごとにまとめます。"
    description = "`annofabcli statistics visualize`コマンドの出力ファイルである複数の'全体の生産性と品質.csv'の値をプロジェクトごとにまとめます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
