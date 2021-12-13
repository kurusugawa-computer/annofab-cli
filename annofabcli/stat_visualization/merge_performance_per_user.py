import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_USER
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance

logger = logging.getLogger(__name__)


def merge_user_performance(csv_path_list: List[Path]) -> UserPerformance:
    """
    `メンバごとの生産性と品質.csv` をマージしたDataFrameをラップするオブジェクトを返す。


    """
    obj_list = []
    for csv_path in csv_path_list:
        if csv_path.exists():
            obj_list.append(UserPerformance.from_csv(csv_path))
        else:
            logger.warning(f"{csv_path} は存在しませんでした。")
            continue

    if len(obj_list) == 0:
        logger.warning(f"マージ対象のCSVファイルは存在しませんでした。")
        return pandas.DataFrame()

    sum_obj = UserPerformance(obj_list[0])
    for obj in obj_list[1:]:
        sum_obj = UserPerformance.merge(sum_obj, obj)
    return sum_obj


def merge_performance_per_user(csv_path_list: List[Path], output_path: Path):
    obj = merge_user_performance(csv_path_list)
    obj.to_csv(output_path)


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
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである ``{FILENAME_PERFORMANCE_PER_USER}`` のパスを指定してください。"),
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "merge_performance_csv_per_user"
    subcommand_help = f"``annofabcli statistics visualize`` コマンドの出力ファイル ``{FILENAME_PERFORMANCE_PER_USER}`` をマージします"
    description = f"``annofabcli statistics visualize`` コマンドの出力ファイル ``{FILENAME_PERFORMANCE_PER_USER}`` をマージします"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
