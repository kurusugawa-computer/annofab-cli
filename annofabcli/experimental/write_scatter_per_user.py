import argparse
import logging

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.utils import _read_multiheader_csv
from annofabcli.statistics.scatter import Scatter

logger = logging.getLogger(__name__)


class WriteScatterPerUser(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        scatter_obj = Scatter(outdir=args.output_dir, project_id=project_id)

        df = _read_multiheader_csv(args.csv)
        scatter_obj = Scatter(outdir=args.output_dir, project_id=project_id)
        scatter_obj.write_scatter_for_productivity_by_monitored_worktime(df)
        scatter_obj.write_scatter_for_productivity_by_actual_worktime(df)
        scatter_obj.write_scatter_for_quality(df)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WriteScatterPerUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help=("CSVファイルのパスを指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'メンバごとの生産性と品質.csv'と同じフォーマットです。"),
    )
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_scatter_per_user"
    subcommand_help = "CSVからユーザごとにプロットした散布図を出力します。"
    description = "CSVからユーザごとにプロットした散布図を出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
