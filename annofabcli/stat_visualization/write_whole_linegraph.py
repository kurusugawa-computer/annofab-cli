import argparse
import logging
from pathlib import Path

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.statistics.linegraph import LineGraph

logger = logging.getLogger(__name__)


def write_whole_linegraph(csv: Path, output_dir: Path) -> None:
    df = pandas.read_csv(str(csv))
    linegraph_obj = LineGraph(outdir=str(output_dir))
    linegraph_obj.write_whole_productivity_line_graph(df)
    linegraph_obj.write_whole_cumulative_line_graph(df)


class WriteWholeLingraph(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        write_whole_linegraph(csv=args.csv, output_dir=args.output_dir)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WriteWholeLingraph(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=("CSVファイルのパスを指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'日毎の生産量と生産性.csv'と同じフォーマットです。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_whole_linegraph"
    subcommand_help = "CSVからプロジェクト全体の生産量と生産性の折れ線グラフを出力します。"
    description = "CSVからプロジェクト全体の生産量と生産性の折れ線グラフを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
