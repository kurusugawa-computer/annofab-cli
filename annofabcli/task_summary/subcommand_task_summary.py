import argparse

import annofabcli.common.cli
import annofabcli.task_summary.phase_status


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.task_summary.phase_status.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "task_summary"
    subcommand_help = "タスクのサマリー情報関係のサブコマンド"
    description = "タスクのサマリー情報関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
