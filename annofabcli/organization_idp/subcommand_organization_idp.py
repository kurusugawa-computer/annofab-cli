import argparse

import annofabcli.common.cli
import annofabcli.organization_idp.list_organization_idp


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name")

    annofabcli.organization_idp.list_organization_idp.add_parser(subparsers)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "organization_idp"
    subcommand_help = "組織IDプロバイダー関係のサブコマンド"
    description = "組織IDプロバイダー関係のサブコマンド"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
