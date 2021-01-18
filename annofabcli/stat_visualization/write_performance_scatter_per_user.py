import argparse
import logging
from pathlib import Path

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.csv import FILENAME_PEFORMANCE_PER_USER
from annofabcli.statistics.scatter import Scatter

logger = logging.getLogger(__name__)


def write_performance_scatter_per_user(csv: Path, output_dir: Path) -> None:
    df = read_multiheader_csv(str(csv))
    scatter_obj = Scatter(str(output_dir))
    scatter_obj.write_scatter_for_productivity_by_monitored_worktime(df)
    scatter_obj.write_scatter_for_productivity_by_actual_worktime(df)
    scatter_obj.write_scatter_for_quality(df)
    scatter_obj.write_scatter_for_productivity_by_actual_worktime_and_quality(df)


class WriteScatterPerUser(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        write_performance_scatter_per_user(csv=args.csv, output_dir=args.output_dir)


def main(args):
    WriteScatterPerUser(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=(f"`annofabcli statistics visualize`コマンドの出力ファイルである'{FILENAME_PEFORMANCE_PER_USER}'のパスを指定してください。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_performance_scatter_per_user"
    subcommand_help = (
        f"`annofabcli statistics visualize`コマンドの出力ファイルである'{FILENAME_PEFORMANCE_PER_USER}'から、ユーザごとにプロットした散布図を出力します。"
    )
    description = (
        f"`annofabcli statistics visualize`コマンドの出力ファイルである'{FILENAME_PEFORMANCE_PER_USER}'から、ユーザごとにプロットした散布図を出力します。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
