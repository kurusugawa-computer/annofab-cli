import argparse
import json
import logging

import pandas
from annofabapi.models import ProjectMemberRole, Webhook

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


def create_webhook_dataframe(webhook_list: list[Webhook]) -> pandas.DataFrame:
    """
    Webhook一覧のDataFrameを作成する。

    Args:
        webhook_list: Webhook一覧

    Returns:
        Webhook一覧のDataFrame
    """
    prior_columns = [
        "project_id",
        "webhook_id",
        "webhook_status",
        "event_type",
        "method",
        "url",
        "headers",
        "body",
        "created_datetime",
        "updated_datetime",
    ]
    df = pandas.DataFrame(webhook_list)
    if df.empty:
        return pandas.DataFrame(columns=prior_columns)

    if "headers" in df.columns:
        df["headers"] = df["headers"].map(lambda e: json.dumps(e, ensure_ascii=False))

    columns = get_columns_with_priority(df, prior_columns=prior_columns)
    return df[columns]


class ListWebhook(CommandLine):
    """
    Webhook一覧を表示する。
    """

    def get_webhook_list(self, project_id: str) -> list[Webhook]:
        """
        Webhook一覧を取得する。

        Args:
            project_id: 対象プロジェクトのproject_id

        Returns:
            Webhook一覧
        """
        self.validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])
        webhook_list, _ = self.service.api.get_webhooks(project_id)
        return webhook_list

    def main(self) -> None:
        args = self.args
        webhook_list = self.get_webhook_list(args.project_id)
        logger.info(f"Webhook一覧の件数: {len(webhook_list)}")

        if args.format == OutputFormat.CSV.value:
            df = create_webhook_dataframe(webhook_list)
            self.print_csv(df)
        else:
            self.print_according_to_format(webhook_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWebhook(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "Webhook一覧を出力します。"
    description = "Webhook一覧を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
