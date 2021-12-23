import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_DATE
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import WholeProductivityPerCompletedDate

logger = logging.getLogger(__name__)


def write_whole_linegraph(csv: Path, output_dir: Path) -> None:
    df = pandas.read_csv(str(csv))
    obj = WholeProductivityPerCompletedDate(df)
    obj.plot(output_dir / "折れ線-横軸_日-全体.html")
    obj.plot_cumulatively(output_dir / "累積折れ線-横軸_日-全体.html")


class WriteWholeLingraph(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        write_whole_linegraph(csv=args.csv, output_dir=args.output_dir)


def main(args):
    WriteWholeLingraph(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_PERFORMANCE_PER_DATE}'のパスを指定してください。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_whole_linegraph"
    subcommand_help = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_PERFORMANCE_PER_DATE}'から、折れ線グラフを出力します。"
    )
    description = f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_PERFORMANCE_PER_DATE}'から、折れ線グラフを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
