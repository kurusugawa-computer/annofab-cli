import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_USER, Csv
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


def create_df_merged_performance_per_user(csv_path_list: List[Path]) -> pandas.DataFrame:
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

    if len(df_list) == 0:
        logger.warning(f"マージ対象のCSVファイルは存在しませんでした。")
        return pandas.DataFrame()

    sum_df = df_list[0]
    for df in df_list[1:]:
        sum_df = Table.merge_productivity_per_user_from_aw_time(sum_df, df)
    return sum_df


def merge_performance_per_user(csv_path_list: List[Path], output_path: Path):
    sum_df = create_df_merged_performance_per_user(csv_path_list)
    if len(sum_df) == 0:
        logger.warning(f"出力対象のデータが0件であるため、CSVファイルを出力しません。")
        return

    csv_obj = Csv(outdir=str(output_path.parent))
    csv_obj.write_productivity_per_user(sum_df, output_path=output_path)


class MergePerformancePerUser(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        merge_performance_per_user(csv_path_list=args.csv, output_path=args.output)


def main(args):
    MergePerformancePerUser(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_PERFORMANCE_PER_USER}'のパスを指定してください。"),
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "merge_performance_csv_per_user"
    subcommand_help = f"``annofabcli statistics visualize`` コマンドの出力ファイル'{FILENAME_PERFORMANCE_PER_USER}'をマージします"
    description = f"``annofabcli statistics visualize`` コマンドの出力ファイル'{FILENAME_PERFORMANCE_PER_USER}'をマージします"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
