import argparse
import logging
from pathlib import Path
from typing import Optional

import annofabcli
from annofabcli.statistics.csv import FILENAME_WHOLE_PERFORMANCE
from annofabcli.statistics.visualization.dataframe.project_performance import ProjectPerformance
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


def main(args):
    root_dir: Path = args.dir
    project_dir_list = [ProjectDir(elm) for elm in root_dir.iterdir() if elm.is_dir()]

    project_performance = ProjectPerformance.from_project_dirs(project_dir_list)
    project_performance.to_csv(args.output)


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"プロジェクトディレクトリが存在するディレクトリを指定してください。プロジェクトディレクトリ内の ``{FILENAME_WHOLE_PERFORMANCE}`` というファイルを読み込みます。",
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "summarise_whole_performance_csv"
    subcommand_help = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである複数の'{FILENAME_WHOLE_PERFORMANCE}'の値をプロジェクトごとにまとめます。"
    )
    description = (
        f"``annofabcli statistics visualize`` コマンドの出力ファイルである複数の'{FILENAME_WHOLE_PERFORMANCE}'の値をプロジェクトごとにまとめます。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
