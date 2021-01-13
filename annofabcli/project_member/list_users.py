import argparse
import logging
from typing import List

import pandas
import requests
from annofabapi.models import ProjectMember

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.utils import get_columns_with_priority
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListUser(AbstractCommandLineInterface):
    """
    ユーザを表示する
    """

    PRIOR_COLUMNS = [
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

    def get_all_project_members(self, project_id: str, include_inactive: bool = False):
        query_params = {}
        if include_inactive:
            query_params.update({"include_inactive_member": ""})

        project_members = self.service.wrapper.get_all_project_members(project_id, query_params=query_params)
        return project_members

    def get_project_members_with_project_id(
        self, project_id_list: List[str], include_inactive: bool = False
    ) -> List[ProjectMember]:
        all_project_members: List[ProjectMember] = []

        for project_id in project_id_list:
            try:
                project, _ = self.service.api.get_project(project_id)
            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"project_id = {project_id} のプロジェクトにアクセスできなかった（存在しないproject_id、またはプロジェクトメンバでない）")
                continue

            project_title = project["title"]
            project_members = self.get_all_project_members(project_id, include_inactive=include_inactive)
            logger.info(f"{project_title} のプロジェクトメンバを {len(project_members)} 件取得した。project_id={project_id}")

            for member in project_members:
                AddProps.add_properties_of_project(member, project_title)

            all_project_members.extend(project_members)

        return all_project_members

    def main(self):
        args = self.args

        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
        project_members = self.get_project_members_with_project_id(
            project_id_list,
            include_inactive=args.include_inactive,
        )

        logger.info(f"プロジェトメンバ一覧の件数: {len(project_members)}")
        if args.format == FormatArgument.CSV.value:
            project_members = self.search_with_jmespath_expression(project_members)
            df = pandas.DataFrame(project_members)
            columns = get_columns_with_priority(df, prior_columns=self.PRIOR_COLUMNS)
            self.print_csv(df[columns])
        else:
            self.print_according_to_format(project_members)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    list_group = parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="ユーザを表示するプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--include_inactive", action="store_true", help="脱退しているメンバも出力します。")

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
    subcommand_help = "複数のプロジェクトのプロジェクトメンバを出力します。"
    description = "複数のプロジェクトのプロジェクトメンバを出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
