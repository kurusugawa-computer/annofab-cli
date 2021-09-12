import argparse
import logging
from typing import Any, Dict, List, Optional

import pandas
import requests

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


class ListOrganizationMember(AbstractCommandLineInterface):
    """
    組織メンバ一覧を表示する。
    """

    PRIOR_COLUMNS = [
        "organization_id",
        "organization_name",
        "account_id",
        "user_id",
        "username",
        "biography",
        "role",
        "status",
    ]

    def get_organization_member_list(self, organization_name: str) -> List[Dict[str, Any]]:
        organization_member_list = self.service.wrapper.get_all_organization_members(organization_name)
        logger.debug(f"組織メンバ一覧の件数: {len(organization_member_list)}")
        if len(organization_member_list) == 10000:
            logger.warning("組織メンバ一覧は10,000件で打ち切られている可能性があります。")

        for organization_member in organization_member_list:
            organization_member["organization_name"] = organization_name
        return organization_member_list

    def main(self):
        args = self.args
        organization_name_list = annofabcli.common.cli.get_list_from_args(args.organization)

        organization_member_list = []
        for organization_name in organization_name_list:
            try:
                organization_member_list.extend(self.get_organization_member_list(organization_name))
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"{organization_name} の組織メンバを取得できませんでした。")
                continue

        if args.format == FormatArgument.CSV.value:
            organization_member_list = self.search_with_jmespath_expression(organization_member_list)
            df = pandas.DataFrame(organization_member_list)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            self.print_csv(df[columns])
        else:
            self.print_according_to_format(organization_member_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListOrganizationMember(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "-org",
        "--organization",
        required=True,
        type=str,
        nargs="+",
        help="出力対象の組織名を指定してください。 ``file://`` を先頭に付けると、組織名の一覧が記載されたファイルを指定できます。",
    )

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.USER_ID_LIST],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "list"
    subcommand_help = "組織メンバ一覧を出力します。"
    description = "組織メンバ一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
