import argparse
import json
import logging

import pandas
from annofabapi.models import OrganizationPlugin, OrganizationPluginList

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


def create_organization_plugin_dataframe(plugin_list: list[OrganizationPlugin]) -> pandas.DataFrame:
    """
    組織プラグイン一覧のDataFrameを作成する。

    Args:
        plugin_list: 組織プラグイン一覧

    Returns:
        組織プラグイン一覧のDataFrame
    """
    prior_columns = [
        "organization_id",
        "plugin_id",
        "plugin_name",
        "description",
        "is_builtin",
        "project_extra_data_kinds",
        "detail",
        "created_datetime",
        "updated_datetime",
    ]
    df = pandas.DataFrame(plugin_list)
    if df.empty:
        return pandas.DataFrame(columns=prior_columns)

    for column in ["project_extra_data_kinds", "detail"]:
        if column in df.columns:
            df[column] = df[column].map(lambda e: json.dumps(e, ensure_ascii=False))

    columns = get_columns_with_priority(df, prior_columns=prior_columns)
    return df[columns]


class ListOrganizationPlugin(CommandLine):
    """
    組織プラグイン一覧を表示する。
    """

    def get_organization_plugin_list(self, organization_name: str) -> list[OrganizationPlugin]:
        """
        組織プラグイン一覧を取得する。

        Args:
            organization_name: 対象組織の組織名

        Returns:
            組織プラグイン一覧
        """
        plugin_list_obj: OrganizationPluginList
        plugin_list_obj, _ = self.service.api.get_organization_plugins(organization_name)
        return plugin_list_obj["list"]

    def main(self) -> None:
        args = self.args
        plugin_list = self.get_organization_plugin_list(args.organization)
        logger.info(f"組織プラグイン一覧の件数: {len(plugin_list)}")

        if args.format == OutputFormat.CSV.value:
            df = create_organization_plugin_dataframe(plugin_list)
            self.print_csv(df)
        else:
            self.print_according_to_format(plugin_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListOrganizationPlugin(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-org", "--organization", type=str, required=True, help="対象の組織名を指定してください。")

    argument_parser = annofabcli.common.cli.ArgumentParser(parser)
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "組織プラグイン一覧を出力します。"
    description = "組織プラグイン一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
