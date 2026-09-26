from __future__ import annotations

import argparse
import json
import logging

import pandas
from annofabapi.models import PersonalAccessTokenInfo

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


def create_personal_access_token_dataframe(personal_access_token_list: list[PersonalAccessTokenInfo]) -> pandas.DataFrame:
    """
    パーソナルアクセストークン一覧のDataFrameを作成する。

    Args:
        personal_access_token_list: パーソナルアクセストークン一覧

    Returns:
        パーソナルアクセストークン一覧のDataFrame
    """
    prior_columns = ["note", "id", "permissions", "created_datetime", "last_used_datetime", "expired_datetime", "account_id"]
    df = pandas.DataFrame(personal_access_token_list)
    if df.empty:
        return pandas.DataFrame(columns=prior_columns)

    if "permissions" in df.columns:
        df["permissions"] = df["permissions"].map(lambda permissions: json.dumps(permissions, ensure_ascii=False))

    columns = get_columns_with_priority(df, prior_columns=prior_columns)
    return df[columns]


class ListPersonalAccessToken(CommandLine):
    """パーソナルアクセストークン一覧を出力する。"""

    def main(self) -> None:
        personal_access_token_list, _ = self.service.api.get_personal_access_tokens()
        logger.info(f"パーソナルアクセストークン一覧の件数: {len(personal_access_token_list)}")

        if self.args.format == OutputFormat.CSV.value:
            self.print_csv(create_personal_access_token_dataframe(personal_access_token_list))
        else:
            self.print_according_to_format(personal_access_token_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListPersonalAccessToken(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_personal_access_token"
    subcommand_help = "パーソナルアクセストークン一覧を出力します。"
    description = "パーソナルアクセストークン一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
