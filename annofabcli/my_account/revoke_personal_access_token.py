from __future__ import annotations

import argparse
import logging

import annofabapi

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class RevokePersonalAccessToken(CommandLine):
    """パーソナルアクセストークンを無効化する。"""

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace) -> None:
        super().__init__(service, facade, args)

    def main(self) -> None:
        personal_access_token_id = self.args.personal_access_token_id
        if not self.confirm_processing(f"パーソナルアクセストークン id='{personal_access_token_id}' を無効化しますか？"):
            return

        self.service.api.revoke_personal_access_token(request_body={"id": personal_access_token_id})
        logger.info(f"パーソナルアクセストークン id='{personal_access_token_id}' を無効化しました。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    RevokePersonalAccessToken(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--personal_access_token_id", type=str, required=True, help="無効化するパーソナルアクセストークンのIDを指定します。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "revoke_personal_access_token"
    subcommand_help = "パーソナルアクセストークンを無効化します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
