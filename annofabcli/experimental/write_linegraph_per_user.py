import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.statistics.linegraph import LineGraph
from annofabcli.statistics.table import Table

logger = logging.getLogger(__name__)


def write_linegraph_by_user(csv: Path, output_dir: Path, user_id_list: Optional[List[str]] = None) -> None:
    """
    折れ線グラフをユーザごとにプロットする。

    Args:
        user_id_list: 折れ線グラフに表示するユーザ

    Returns:

    """
    task_df = pandas.read_csv(str(csv))
    if len(task_df) == 0:
        logger.warning(f"タスク一覧が0件のため、折れ線グラフを出力しません。")
        return

    linegraph_obj = LineGraph(outdir=str(output_dir))

    task_cumulative_df_by_annotator = Table.create_cumulative_df_by_first_annotator(task_df)
    linegraph_obj.write_cumulative_line_graph_for_annotator(
        df=task_cumulative_df_by_annotator, first_annotation_user_id_list=user_id_list,
    )

    task_cumulative_df_by_inspector = Table.create_cumulative_df_by_first_inspector(task_df)
    linegraph_obj.write_cumulative_line_graph_for_inspector(
        df=task_cumulative_df_by_inspector, first_inspection_user_id_list=user_id_list,
    )

    task_cumulative_df_by_acceptor = Table.create_cumulative_df_by_first_acceptor(task_df)
    linegraph_obj.write_cumulative_line_graph_for_acceptor(
        df=task_cumulative_df_by_acceptor, first_acceptance_user_id_list=user_id_list,
    )

    df_by_date_user = Table.create_dataframe_by_date_user(task_df)
    linegraph_obj.write_productivity_line_graph_for_annotator(
        df=df_by_date_user, first_annotation_user_id_list=user_id_list
    )


class WriteLingraphPerUser(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        write_linegraph_by_user(csv=args.csv, output_dir=args.output_dir, user_id_list=user_id_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WriteLingraphPerUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=("CSVファイルのパスを指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'タスクlist.csv'と同じフォーマットです。"),
    )

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "絞り込み条件となるユーザのuser_idを指定してください。" "指定しない場合は、上位20人のユーザ情報がプロットされます。" "file://`を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_linegraph_per_user"
    subcommand_help = "CSVからユーザごとの指標を折れ線グラフで出力します。"
    description = "CSVからユーザごとの指標を折れ線グラフで出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
