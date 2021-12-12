import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.csv import FILENAME_TASK_LIST
from annofabcli.statistics.linegraph import LineGraph, OutputTarget
from annofabcli.statistics.table import Table
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)

logger = logging.getLogger(__name__)


def write_linegraph_per_user(
    csv: Path, output_dir: Path, user_id_list: Optional[List[str]] = None, minimal_output: bool = False
) -> None:
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

    output_target_list: Optional[List[OutputTarget]] = None
    if minimal_output:
        output_target_list = [OutputTarget.ANNOTATION]

    task_df = Table.create_gradient_df(task_df)
    task_cumulative_df_by_annotator = Table.create_cumulative_df_by_first_annotator(task_df)
    linegraph_obj.write_cumulative_line_graph_for_annotator(
        df=task_cumulative_df_by_annotator,
        output_target_list=output_target_list,
        first_annotation_user_id_list=user_id_list,
    )

    task_cumulative_df_by_inspector = Table.create_cumulative_df_by_first_inspector(task_df)
    linegraph_obj.write_cumulative_line_graph_for_inspector(
        df=task_cumulative_df_by_inspector,
        output_target_list=output_target_list,
        first_inspection_user_id_list=user_id_list,
    )

    task_cumulative_df_by_acceptor = Table.create_cumulative_df_by_first_acceptor(task_df)
    linegraph_obj.write_cumulative_line_graph_for_acceptor(
        df=task_cumulative_df_by_acceptor,
        output_target_list=output_target_list,
        first_acceptance_user_id_list=user_id_list,
    )

    if not minimal_output:
        # 各ユーザごとの日ごとの情報
        annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(task_df)
        annotator_per_date_obj.plot_annotation_metrics(
            Path("教師付者用/折れ線-横軸_教師付開始日-縦軸_アノテーション単位の指標-教師付者用.html"), user_id_list
        )
        annotator_per_date_obj.plot_input_data_metrics(
            Path("教師付者用/折れ線-横軸_教師付開始日-縦軸_入力データ単位の指標-教師付者用.html"), user_id_list
        )

        inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(task_df)
        inspector_per_date_obj.plot_annotation_metrics(
            Path("検査者用/折れ線-横軸_検査開始日-縦軸_アノテーション単位の指標-検査者用.html"), user_id_list
        )
        inspector_per_date_obj.plot_input_data_metrics(Path("検査者用/折れ線-横軸_検査開始日-縦軸_入力データ単位の指標-検査者用.html"), user_id_list)

        acceptor_per_date = AcceptorProductivityPerDate.from_df_task(task_df)
        acceptor_per_date.plot_annotation_metrics(Path("検査者用/折れ線-横軸_検査開始日-縦軸_アノテーション単位の指標-検査者用.html"), user_id_list)
        acceptor_per_date.plot_input_data_metrics(Path("検査者用/折れ線-横軸_検査開始日-縦軸_入力データ単位の指標-検査者用.html"), user_id_list)


class WriteLingraphPerUser(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        write_linegraph_per_user(
            csv=args.csv, output_dir=args.output_dir, user_id_list=user_id_list, minimal_output=args.minimal
        )


def main(args):
    WriteLingraphPerUser(args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'のパスを指定してください。"),
    )

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "折れ線グラフにプロットするユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人のユーザ情報がプロットされます。"
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_linegraph_per_user"
    subcommand_help = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'から、ユーザごとの指標をプロットした折れ線グラフを出力します。"
    )
    description = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{FILENAME_TASK_LIST}'から、ユーザごとの指標をプロットした折れ線グラフを出力します。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
