import argparse

import annofabcli.project.change_organization_of_project
import annofabcli.project.change_project_status
import annofabcli.project.copy_project
import annofabcli.project.create_project
import annofabcli.project.diff_projects
import annofabcli.project.list_project
import annofabcli.project.update_configuration
import annofabcli.project.update_project
from annofabcli.common.cli import create_parser as common_create_parser


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    # サブコマンドの定義
    annofabcli.project.change_organization_of_project.create_parser(subparsers)
    annofabcli.project.change_project_status.create_parser(subparsers)
    annofabcli.project.copy_project.create_parser(subparsers)
    annofabcli.project.create_project.create_parser(subparsers)
    annofabcli.project.diff_projects.create_parser(subparsers)
    annofabcli.project.list_project.create_parser(subparsers)
    annofabcli.project.update_project.create_parser(subparsers)
    annofabcli.project.update_configuration.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "project"
    subcommand_help = "プロジェクト関係のサブコマンド"
    description = "プロジェクト関係のサブコマンド"

    parser = common_create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
