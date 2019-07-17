import annofabcli
import annofabcli.common.cli
import annofabcli.task.reject_tasks
import argparse

def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.task.reject_tasks.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "task"
    subcommand_help = "タスク関係のサブコマンド"
    description = "タスク関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
