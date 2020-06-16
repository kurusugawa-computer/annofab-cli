import argparse
import logging

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.statistics.csv import Csv
from annofabcli.statistics.table import Table
from pathlib import Path
logger = logging.getLogger(__name__)


class WritePerfomancePerUser(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        project_id = args.project_id
        csv_obj = Csv(outdir=args.output_dir, filename_prefix=project_id[0:8])

        df_task = pandas.read_csv(args.task_csv)
        df_task_history = pandas.read_csv(args.task_history_csv)
        df_labor = pandas.read_csv(args.labor_csv)

        df_count_ratio = Table.create_annotation_count_ratio_df(df_task_history, df_task)

        df_perfomance_per_user = Table.create_productivity_per_user_from_aw_time(
            df_task_history, df_labor, df_count_ratio
        )

        csv_obj.write_productivity_from_aw_time(df_perfomance_per_user)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WritePerfomancePerUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument(
        "--csv",
        type=Path,
        nargs="+",
        required=True,
        help=("CSVファイルのパスを複数指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'メンバごとの生産性と品質.csv'と同じフォーマットです。"),
    )

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "sum_peformance_per_user"
    subcommand_help = "複数の'メンバごとの生産性と品質.csv'の値をまとめて出力します。"
    description = "複数の'メンバごとの生産性と品質.csv'の値をまとめて出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
