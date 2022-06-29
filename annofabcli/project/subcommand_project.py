import argparse
from typing import Optional

import annofabcli.project.change_project_status
import annofabcli.project.copy_project
import annofabcli.project.diff_projects
import annofabcli.project.download
import annofabcli.project.list_project
import annofabcli.project.update_annotation_zip
from annofabcli.common.cli import add_parser as common_add_parser


def parse_args(parser: argparse.ArgumentParser):

    subparsers = parser.add_subparsers(dest="subcommand_name")

    # サブコマンドの定義
    annofabcli.project.change_project_status.add_parser(subparsers)
    annofabcli.project.copy_project.add_parser(subparsers)
    annofabcli.project.diff_projects.add_parser(subparsers)
    annofabcli.project.download.add_parser(subparsers)
    annofabcli.project.list_project.add_parser(subparsers)
    annofabcli.project.update_annotation_zip.add_parser(subparsers)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "project"
    subcommand_help = "プロジェクト関係のサブコマンド"
    description = "プロジェクト関係のサブコマンド"

    parser = common_add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
