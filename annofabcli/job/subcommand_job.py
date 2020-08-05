import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.job.delete_job
import annofabcli.job.list_job
import annofabcli.job.list_last_job


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義

    annofabcli.job.delete_job.add_parser(subparsers)
    annofabcli.job.list_job.add_parser(subparsers)
    annofabcli.job.list_last_job.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "job"
    subcommand_help = "ジョブ関係のサブコマンド"
    description = "ジョブ関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description, is_subcommand=False
    )
    parse_args(parser)
