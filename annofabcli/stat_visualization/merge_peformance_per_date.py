import argparse
import logging
from pathlib import Path
from typing import List

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_PEFORMANCE_PER_DATE, Csv
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


def create_df_merged_peformance_per_date(csv_path_list: List[Path]) -> pandas.DataFrame:
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

    sum_df = df_list[0]
    for df in df_list[1:]:
        sum_df = Table.merge_whole_productivity_per_date(sum_df, df)

    return sum_df


def merge_peformance_per_date(csv_path_list: List[Path], output_path: Path) -> None:
    sum_df = create_df_merged_peformance_per_date(csv_path_list)
    csv_obj = Csv(outdir=str(output_path.parent))
    csv_obj.write_whole_productivity_per_date(sum_df, output_path=output_path)


class MergePerfomancePerDate(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        merge_peformance_per_date(csv_path_list=args.csv, output_path=args.output)


def main(args):
    MergePerfomancePerDate(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=(f"`annofabcli statistics visualize`コマンドの出力ファイルである'{FILENAME_PEFORMANCE_PER_DATE}'のパスを指定してください。"),
    )

    parser.add_argument("-o", "--output", required=True, type=Path, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "merge_peformance_csv_per_date"
    subcommand_help = f"`annofabcli statistics visualize`コマンドの出力ファイル'{FILENAME_PEFORMANCE_PER_DATE}'をマージします。"
    description = f"`annofabcli statistics visualize`コマンドの出力ファイル'{FILENAME_PEFORMANCE_PER_DATE}'をマージします。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
