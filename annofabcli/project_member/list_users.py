import argparse
import logging

import pandas
from annofabapi.models import ProjectMember

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import get_columns_with_priority

logger = logging.getLogger(__name__)


class ListProjectMembers(CommandLine):
    """
    プロジェクトメンバを表示する
    """

    PRIOR_COLUMNS = [  # noqa: RUF012
        "project_id",
        "project_title",
        "account_id",
        "user_id",
        "username",
        "biography",
        "member_status",
        "member_role",
        "sampling_inspection_rate",
        "sampling_acceptance_rate",
    ]

    def get_all_project_members(self, project_id: str, include_inactive: bool = False) -> list[ProjectMember]:  # noqa: FBT001, FBT002
        """指定したプロジェクトのメンバを、プロジェクト名を付けて取得する。

        Args:
            project_id: 対象のプロジェクトID
            include_inactive: 脱退済みのメンバも取得するか

        Returns:
            プロジェクトメンバ一覧
        """
        query_params = {}
        if include_inactive:
            query_params.update({"include_inactive_member": ""})

        project, _ = self.service.api.get_project(project_id)
        project_members = self.service.wrapper.get_all_project_members(project_id, query_params=query_params)
        for member in project_members:
            member["project_title"] = project["title"]
        return project_members

    def main(self) -> None:
        args = self.args

        project_members = self.get_all_project_members(
            args.project_id,
            include_inactive=args.include_inactive,
        )

        logger.info(f"プロジェクトメンバ一覧の件数: {len(project_members)}")
        if args.format == OutputFormat.CSV.value:
            df = pandas.DataFrame(project_members) if project_members else pandas.DataFrame(columns=self.PRIOR_COLUMNS)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            self.print_csv(df[columns])
        else:
            self.print_according_to_format(project_members)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument("--include_inactive", action="store_true", help="脱退しているメンバも出力します。")

    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON, OutputFormat.USER_ID_LIST],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list"
    subcommand_help = "プロジェクトメンバを出力します。"
    description = "指定したプロジェクトのプロジェクトメンバを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
