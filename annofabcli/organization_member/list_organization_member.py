import argparse
import logging

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument

logger = logging.getLogger(__name__)


class ListOrganizationMember(AbstractCommandLineInterface):
    """
    組織メンバ一覧を表示する。
    """

    def print_organization_member_list(self, organization_name: str):
        """
        組織メンバ一覧を出力する
        """

        organization_member_list = self.service.wrapper.get_all_organization_members(organization_name)
        logger.debug(f"組織メンバ一覧の件数: {len(organization_member_list)}")
        if len(organization_member_list) == 10000:
            logger.warning("組織メンバ一覧は10,000件で打ち切られている可能性があります。")

        self.print_according_to_format(organization_member_list)

    def main(self):
        args = self.args
        self.print_organization_member_list(args.organization)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListOrganizationMember(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    parser.add_argument("-org", "--organization", required=True, type=str, help="対象の組織名を指定してください。")

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.USER_ID_LIST],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "組織メンバ一覧を出力します。"
    description = "組織メンバ一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
