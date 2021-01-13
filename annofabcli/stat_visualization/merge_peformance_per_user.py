import argparse
import logging
from pathlib import Path
from typing import List

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.csv import Csv
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


def create_df_merged_peformance_per_user(csv_path_list: List[Path]) -> pandas.DataFrame:
    """
    `メンバごとの生産性と品質.csv` をマージしたDataFrameを返す。

    Args:
        csv_path_list:

    Returns:

    """
    df_list: List[pandas.DataFrame] = []
    for csv_path in csv_path_list:
        if csv_path.exists():
            df = read_multiheader_csv(str(csv_path))
            df_list.append(df)
        else:
            logger.warning(f"{csv_path} は存在しませんでした。")
            continue

    sum_df = df_list[0]
    for df in df_list[1:]:
        sum_df = Table.merge_productivity_per_user_from_aw_time(sum_df, df)
    return sum_df


def merge_peformance_per_user(csv_path_list: List[Path], output_path: Path):
    sum_df = create_df_merged_peformance_per_user(csv_path_list)
    csv_obj = Csv(outdir=str(output_path.parent))
    csv_obj.write_productivity_per_user(sum_df, output_path=output_path)


class MergePerfomancePerUser(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        merge_peformance_per_user(csv_path_list=args.csv, output_path=args.output)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    MergePerfomancePerUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=("CSVファイルのパスを複数指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'メンバごとの生産性と品質.csv'と同じフォーマットです。"),
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "merge_peformance_per_user"
    subcommand_help = "複数の'メンバごとの生産性と品質.csv'の値をまとめて出力します。"
    description = "複数の'メンバごとの生産性と品質.csv'の値をまとめて出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
