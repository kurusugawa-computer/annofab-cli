import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_TASK_LIST
from annofabcli.statistics.visualization.dataframe.task import Task

logger = logging.getLogger(__name__)


def write_task_histogram(csv: Path, output_dir: Path) -> None:
    """
    ヒストグラムを出力する
    """
    task_df = pandas.read_csv(str(csv))
    if len(task_df) == 0:
        logger.warning(f"タスク一覧が0件のため、グラフを出力しません。")
        return

    obj = Task(task_df)
    obj.plot_histogram_of_worktime(output_dir / "ヒストグラム-作業時間.html")
    obj.plot_histogram_of_others(output_dir / "ヒストグラム.html")


class WriteTaskHistogram(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        write_task_histogram(csv=args.csv, output_dir=args.output_dir)


def main(args):
    WriteTaskHistogram(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'のパスを指定してください。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_task_histogram"
    subcommand_help = f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'から、ヒストグラムを出力します。"
    description = f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'から、ヒストグラムを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
