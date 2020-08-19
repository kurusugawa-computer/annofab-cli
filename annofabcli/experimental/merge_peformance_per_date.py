import argparse
import logging
from pathlib import Path
from typing import List

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.statistics.csv import Csv
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


class MergePerfomancePerDate(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        df_list: List[pandas.DataFrame] = []
        csv_path_list = args.csv
        for csv_path in csv_path_list:
            df = pandas.read_csv(str(csv_path))
            df_list.append(df)

        sum_df = df_list[0]
        for df in df_list[1:]:
            sum_df = Table.merge_whole_productivity_per_date(sum_df, df)

        output_path: Path = args.output
        csv_obj = Csv(outdir=str(output_path.parent))
        csv_obj.write_whole_productivity_per_date(sum_df, output_path=output_path)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    MergePerfomancePerDate(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=("CSVファイルのパスを複数指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'日毎の生産量と生産性.csv'と同じフォーマットです。"),
    )

    parser.add_argument("-o", "--output", required=True, type=Path, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "merge_peformance_per_date"
    subcommand_help = "`statistics visualize`コマンドの出力ファイルである複数の'日ごとの生産量と生産性.csv'の値をまとめて出力します。"
    description = "`statistics visualize`コマンドの出力ファイルである複数の'日ごとの生産量と生産性.csv'の値をまとめて出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
