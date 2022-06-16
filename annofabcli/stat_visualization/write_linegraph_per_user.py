import argparse
import logging
from pathlib import Path
from typing import List, Optional

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface
from annofabcli.statistics.table import Table
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)



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
        help=(f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{ProjectDir.FILENAME_TASK_LIST}'のパスを指定してください。"),
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
    subcommand_help = f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{ProjectDir.FILENAME_TASK_LIST}'から、ユーザごとの指標をプロットした折れ線グラフを出力します。"
    description = f"``annofabcli statistics visualize`` コマンドの出力ファイルである'{ProjectDir.FILENAME_TASK_LIST}'から、ユーザごとの指標をプロットした折れ線グラフを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
