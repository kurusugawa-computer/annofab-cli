from __future__ import annotations

import argparse
import logging
from typing import Optional

import annofabcli
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    FormatArgument,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class GetMyAccount(CommandLine):
    def main(self) -> None:
        account, _ = self.service.api.get_my_account()
        self.print_according_to_format(account)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    GetMyAccount(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_format(
        choices=[
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
        ],
        default=FormatArgument.PRETTY_JSON,
    )

    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "get"
    subcommand_help = "自分のアカウント情報を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
