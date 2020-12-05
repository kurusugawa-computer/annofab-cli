"""
プロジェクトから複数のユーザを削除する。
"""
import argparse
import logging
from typing import List

import requests

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class DeleteUser(AbstractCommandLineInterface):
    """
    ユーザをプロジェクトから削除する
    """

    def drop_role_with_organization(self, organization_name: str, user_id_list: List[str]):
        projects = self.service.wrapper.get_all_projects_of_organization(
            organization_name, query_params={"account_id": self.service.api.account_id}
        )

        for project in projects:
            project_id = project["project_id"]
            project_title = project["title"]

            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(
                        f"オーナではないため、プロジェクトメンバを脱退させられません。" f"project_id = {project_id}, project_tilte = {project_title}"
                    )
                    continue

                self.service.wrapper.drop_role_to_project_members(project_id, user_id_list)
                logger.info(f"{project_title} からユーザを脱退させました。project_id = {project_id}")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"エラーのため、{project_title} からユーザを脱退させられませんでした。")

    def drop_role_with_project_id(self, project_id_list: List[str], user_id_list: List[str]):
        for project_id in project_id_list:

            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(f"オーナではないため、プロジェクトメンバを脱退させられません。" f"project_id = {project_id}")
                    continue

                project_title = self.service.api.get_project(project_id)[0]["title"]
                self.service.wrapper.drop_role_to_project_members(project_id, user_id_list)
                logger.info(f"{project_title} からユーザを脱退させました。project_id={project_id}")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"エラーのため、project_id = {project_id} からユーザを脱退させられませんでした。")

    def main(self):
        args = self.args
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        if args.organization is not None:
            self.drop_role_with_organization(args.organization, user_id_list)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            self.drop_role_with_project_id(project_id_list, user_id_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="脱退させるユーザのuser_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    drop_group = parser.add_mutually_exclusive_group(required=True)
    drop_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="脱退させるプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    drop_group.add_argument(
        "-org", "--organization", type=str, help="組織名を指定すると、組織配下のすべてのプロジェクト（自分が所属している）から、ユーザを脱退させます。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "delete"
    subcommand_help = "複数のプロジェクトから、ユーザを脱退させます。"
    description = "複数のプロジェクトから、ユーザを脱退させます。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
