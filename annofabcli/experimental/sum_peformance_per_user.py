import argparse
import logging
import numpy
import pandas

import annofabcli
from typing import List, Set, Dict, Any, Optional
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.statistics.csv import Csv
from annofabcli.statistics.table import Table
from pathlib import Path
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.scatter import Scatter


logger = logging.getLogger(__name__)


def get_user_id_set(df_list: List[pandas.DataFrame]) -> Set[str]:
    user_id_set: Set[str] = set()
    for df in df_list:
        user_id_set = user_id_set | set(df["user_id"])
    return user_id_set

def max_last_working_date(date1, date2):
    if numpy.isnan(date1):
        date1 = ""
    if numpy.isnan(date2):
        date2 = ""
    max_date = max(date1, date2)
    if max_date == "":
        return numpy.nan
    else:
        return max_date

def add_df(row1: pandas.Series, row2:pandas.Series) -> pandas.Series:
    sum_row = row1 + row2
    sum_row.loc["username"] = row1["username"]
    sum_row["biography"] = row1["biography"]
    sum_row["last_working_date",""] = max_last_working_date(row1["last_working_date",""], row2["last_working_date",""])
    return sum_row



def sum_df_list(df_list: List[pandas.DataFrame]) -> pandas.DataFrame:
    user_id_set: Set[str] = get_user_id_set(df_list)
    sum_df = df_list[0]
    for df in df_list[1:]:
        for user_id in user_id_set:
            if user_id not in df.index:
                continue
            if user_id in sum_df.index:
                sum_df.loc[user_id] = add_df(sum_df.loc[user_id], df.loc[user_id])
            else:
                sum_df.loc[user_id] = df.loc[user_id]

    return sum_df

def calculate_ratio(df: pandas.DataFrame) -> pandas.DataFrame:
    df[]
    monitored_worktime_ratio
    annotation


class SumPerfomancePerUser(AbstractCommandLineInterface):


    def main(self):
        args = self.args

        df_list: List[pandas.DataFrame] = []
        csv_path_list = args.csv
        for csv_path in csv_path_list:
            df = read_multiheader_csv(str(csv_path))
            df_list.append(df.set_index("user_id"))

        sum_df =
        csv_obj = Csv(outdir=args.output_dir, filename_prefix=project_id[0:8])


        csv_obj.write_productivity_from_aw_time(df_perfomance_per_user)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SumPerfomancePerUser(service, facade, args).main()


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
