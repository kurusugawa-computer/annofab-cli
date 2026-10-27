import argparse

import annofabcli.common.cli
import annofabcli.job.delete_job
import annofabcli.job.list_job
import annofabcli.job.wait_job


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義

    annofabcli.job.delete_job.create_parser(subparsers)
    annofabcli.job.list_job.create_parser(subparsers)
    annofabcli.job.wait_job.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "job"
    subcommand_help = "ジョブ関係のサブコマンド"
    description = "ジョブ関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
