import argparse
import logging
from pathlib import Path
from typing import Optional

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_PERFORMANCE_PER_DATE
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import WholeProductivityPerCompletedDate

logger = logging.getLogger(__name__)


def write_whole_linegraph(whole_productivity: WholeProductivityPerCompletedDate, output_dir: Path) -> None:
    whole_productivity.plot(output_dir / "折れ線-横軸_日-全体.html")
    whole_productivity.plot_cumulatively(output_dir / "累積折れ線-横軸_日-全体.html")


class WriteWholeLingraph(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        whole_productivity = WholeProductivityPerCompletedDate.from_csv(args.csv)
        write_whole_linegraph(whole_productivity, output_dir=args.output_dir)


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
