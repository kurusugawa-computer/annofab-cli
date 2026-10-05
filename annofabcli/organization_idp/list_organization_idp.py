import argparse
import logging
from typing import ClassVar

import pandas
from annofabapi.models import OrganizationOidcIdp

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


class ListOrganizationIdp(CommandLine):
    """組織IDプロバイダー一覧を出力する。"""

    PRIOR_COLUMNS: ClassVar[list[str]] = [
        "organization_name",
        "id",
        "client_id",
        "attributes_request_method",
        "endpoints._type",
        "endpoints.issuer",
        "endpoints.authorize_url",
        "endpoints.token_url",
        "endpoints.userinfo_url",
        "endpoints.jwks_url",
        "attribute_mapping.email",
        "attribute_mapping.name",
        "sign_up_url",
        "created_datetime",
        "updated_datetime",
    ]
    """CSV出力で優先する列。"""

    def main(self) -> None:
        idp_list: list[OrganizationOidcIdp]
        idp_list, _ = self.service.api.get_organization_idp_list(self.args.organization)
        # APIのレスポンスを変更せず、全出力形式からシークレットを除外する。
        output_list = [{key: value for key, value in idp.items() if key != "client_secret"} for idp in idp_list]
        logger.info(f"組織IDプロバイダー一覧の件数: {len(output_list)}")
        if self.args.format == OutputFormat.CSV.value:
            df = pandas.json_normalize(output_list)
            if df.empty:
                df = pandas.DataFrame(columns=self.PRIOR_COLUMNS)
            else:
                columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
                df = df[columns]
            self.print_csv(df)
        else:
            self.print_according_to_format(output_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListOrganizationIdp(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-org", "--organization", type=str, required=True, help="対象の組織名を指定してください。")
    argument_parser = ArgumentParser(parser)
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    description = "組織IDプロバイダー一覧を出力します。クライアントシークレットは出力しません。"
    parser = annofabcli.common.cli.add_parser(subparsers, "list", "組織IDプロバイダー一覧を出力します。", description)
    parse_args(parser)
    return parser
