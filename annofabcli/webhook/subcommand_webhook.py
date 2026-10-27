import argparse

import annofabcli.common.cli
import annofabcli.webhook.list_webhook


def parse_args(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)

    annofabcli.webhook.list_webhook.create_parser(subparsers)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "webhook"
    subcommand_help = "Webhook関係のサブコマンド"
    description = "Webhook関係のサブコマンド"

    parser = annofabcli.common.cli.create_parser(subparsers, subcommand_name, subcommand_help, description, is_subcommand=False)
    parse_args(parser)
    return parser
