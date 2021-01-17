import argparse
import logging
from pathlib import Path

import annofabcli
from annofabcli.statistics.csv import FILENAME_WHOLE_PEFORMANCE, write_summarise_whole_peformance_csv

logger = logging.getLogger(__name__)


def main(args):
    root_dir: Path = args.dir
    csv_path_list = [
        project_dir / FILENAME_WHOLE_PEFORMANCE
        for project_dir in root_dir.iterdir()
        if (project_dir / FILENAME_WHOLE_PEFORMANCE).exists()
    ]
    if len(csv_path_list) > 0:
        write_summarise_whole_peformance_csv(csv_path_list=csv_path_list, output_path=args.output)
    else:
        logger.error(f"{root_dir} 配下に'{FILENAME_WHOLE_PEFORMANCE}'は存在しなかったので、終了します。")
        return


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"プロジェクトディレクトリが存在するディレクトリを指定してください。プロジェクトディレクトリ内の`{FILENAME_WHOLE_PEFORMANCE}`というファイルを読み込みます。",
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "summarise_whole_peformance_csv"
    subcommand_help = (
        f"`annofabcli statistics visualize`コマンドの出力ファイルである複数の'{FILENAME_WHOLE_PEFORMANCE}'の値をプロジェクトごとにまとめます。"
    )
    description = f"`annofabcli statistics visualize`コマンドの出力ファイルである複数の'{FILENAME_WHOLE_PEFORMANCE}'の値をプロジェクトごとにまとめます。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
