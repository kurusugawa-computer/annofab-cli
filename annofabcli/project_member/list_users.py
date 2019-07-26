"""
プロジェクトのユーザを表示する。
"""
import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import requests
from annofabapi.models import ProjectMember

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import FormatArgument
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListUser(AbstractCommandLineInterface):
    """
    ユーザを表示する
    """
    def get_project_members_with_organization(self, organization_name: str) -> List[ProjectMember]:

        # 進行中で自分自身が所属しているプロジェクトの一覧を取得する
        my_account_id = self.facade.get_my_account_id()
        projects = self.service.wrapper.get_all_projects_of_organization(
            organization_name, query_params={
                "status": "active",
                "account_id": my_account_id
            })

        all_project_members: List[ProjectMember] = []

        for project in projects:
            project_id = project["project_id"]
            project_title = project["title"]

            project_members = self.service.wrapper.get_all_project_members(project_id)
            logger.info(f"{project_title} のプロジェクトメンバを取得. project_id={project_id}")

            for member in project_members:
                AddProps.add_properties_of_project(member, project_title)

            all_project_members.extend(project_members)

        return all_project_members

    def get_project_members_with_project_id(self, project_id_list: List[str]) -> List[ProjectMember]:
        all_project_members: List[ProjectMember] = []

        for project_id in project_id_list:
            try:
                project, _ = self.service.api.get_project(project_id)
            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"project_id = {project_id} のプロジェクトにアクセスできなかった（存在しないproject_id、またはプロジェクトメンバでない）")
                continue

            project_title = project["title"]
            project_members = self.service.wrapper.get_all_project_members(project_id)
            logger.info(f"{project_title} のプロジェクトメンバを取得. project_id={project_id}")

            for member in project_members:
                AddProps.add_properties_of_project(member, project_title)

            all_project_members.extend(project_members)

        return all_project_members

    def main(self):
        args = self.args
        csv_format = annofabcli.common.cli.get_csv_format_from_args(args.csv_format)

        project_members = []
        if args.organization is not None:
            project_members = self.get_project_members_with_organization(args.organization)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            project_members = self.get_project_members_with_project_id(project_id_list)

        project_members = self.search_with_jmespath_expression(project_members)
        annofabcli.utils.print_according_to_format(target=project_members, arg_format=FormatArgument(args.format),
                                                   output=args.output, csv_format=csv_format)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ListUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    list_group = parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument('-p', '--project_id', type=str, nargs='+',
                            help='ユーザを表示するプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。')

    list_group.add_argument('-org', '--organization', type=str,
                            help='組織配下のすべての進行中のプロジェクトのプロジェクトメンバを表示したい場合は、組織名を指定してください。')

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON, FormatArgument.USER_ID_LIST],
        default=FormatArgument.CSV)
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list"
    subcommand_help = "複数のプロジェクトのプロジェクトメンバを表示する。"
    description = ("複数のプロジェクトのプロジェクトメンバを表示する。")

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
