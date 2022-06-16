import argparse
import logging
from pathlib import Path
from typing import Optional

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_USER
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


class WriteScatterPerUser(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        user_performance = UserPerformance.from_csv(args.csv)
        project_dir = ProjectDir(args.output_dir)
        project_dir.write_plot_user_performance(user_performance)


def main(args):
    WriteScatterPerUser(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである ``{FILENAME_PERFORMANCE_PER_USER}`` のパスを指定してください。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_performance_scatter_per_user"
    subcommand_help = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである ``{FILENAME_PERFORMANCE_PER_USER}`` "
        "から、ユーザごとにプロットした散布図を出力します。"
    )
    description = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである ``{FILENAME_PERFORMANCE_PER_USER}`` から、"
        "ユーザごとにプロットした散布図を出力します。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
