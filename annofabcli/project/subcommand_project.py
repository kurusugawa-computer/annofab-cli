import argparse

import annofabcli
import annofabcli.common.cli
import annofabcli.project.diff_projects
import annofabcli.project.download


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers()

    # サブコマンドの定義
    annofabcli.project.diff_projects.add_parser(subparsers)
    annofabcli.project.download.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "project"
    subcommand_help = "プロジェクト関係のサブコマンド"
    description = "プロジェクト関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
