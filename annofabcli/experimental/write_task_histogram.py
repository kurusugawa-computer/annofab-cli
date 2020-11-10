import argparse
import importlib
import logging
from pathlib import Path

import pandas

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.common.utils import _catch_exception

logger = logging.getLogger(__name__)


def write_task_histogram(csv: Path, output_dir: Path, minimal_output: bool = False) -> None:
    """
    ヒストグラムを出力する
    """
    task_df = pandas.read_csv(str(csv))
    if len(task_df) == 0:
        logger.warning(f"タスク一覧が0件のため、グラフを出力しません。")
        return

    # holivesのloadに時間がかかって、helpコマンドの出力が遅いため、遅延ロードする
    histogram_module = importlib.import_module("annofabcli.statistics.histogram")
    histogram_obj = histogram_module.Histogram(outdir=str(output_dir))  # type: ignore
    _catch_exception(histogram_obj.write_histogram_for_worktime)(task_df)
    _catch_exception(histogram_obj.write_histogram_for_other)(task_df)

    if not minimal_output:
        _catch_exception(histogram_obj.write_histogram_for_annotation_worktime_by_user)(task_df)
        _catch_exception(histogram_obj.write_histogram_for_inspection_worktime_by_user)(task_df)
        _catch_exception(histogram_obj.write_histogram_for_acceptance_worktime_by_user)(task_df)


class WriteTaskHistogram(AbstractCommandLineInterface):
    def main(self):
        args = self.args
        write_task_histogram(csv=args.csv, output_dir=args.output_dir, minimal_output=args.minimal)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    WriteTaskHistogram(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help=("CSVファイルのパスを指定してください。" "CSVは、'statistics visualize'コマンドの出力結果である'タスクlist.csv'と同じフォーマットです。"),
    )
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_task_histogram"
    subcommand_help = "CSVからタスク関係のヒストグラムを出力します。"
    description = "CSVからタスク関係のヒストグラムを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
