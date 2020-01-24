"""
複数のプロジェクトに、ユーザを招待する。
"""

import argparse
import logging
from typing import List

import requests
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class InviteUser(AbstractCommandLineInterface):
    """
    ユーザをプロジェクトに招待する
    """

    def assign_role_with_organization(self, organization_name: str, user_id_list: List[str], member_role: str):

        # 進行中で自分自身が所属しているプロジェクトの一覧を取得する
        my_account_id = self.facade.get_my_account_id()
        projects = self.service.wrapper.get_all_projects_of_organization(
            organization_name, query_params={"status": "active", "account_id": my_account_id}
        )

        for project in projects:
            project_id = project["project_id"]
            project_title = project["title"]

            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(
                        f"オーナではないため、プロジェクトメンバを招待できません。" f"project_id = {project_id}, project_tilte = {project_title}"
                    )
                    continue

                self.service.wrapper.assign_role_to_project_members(project_id, user_id_list, member_role)
                logger.info(f"{project_title}に招待成功. project_id = {project_id}")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"エラーのため、{project_title} に招待できなかった。")

    def assign_role_with_project_id(self, project_id_list: List[str], user_id_list: List[str], member_role: str):
        for project_id in project_id_list:

            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(f"オーナではないため、プロジェクトメンバを招待できません。" f"project_id = {project_id}")
                    continue

                project_title = self.service.api.get_project(project_id)[0]["title"]
                self.service.wrapper.assign_role_to_project_members(project_id, user_id_list, member_role)
                logger.info(f"{project_title}に招待成功. project_id={project_id}")

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"エラーのため、招待できなかった。project_id={project_id}")

    def main(self):
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        if args.organization is not None:
            self.assign_role_with_organization(args.organization, user_id_list, args.role)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            self.assign_role_with_project_id(project_id_list, user_id_list, args.role)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    InviteUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    role_choices = [
        ProjectMemberRole.OWNER.value,
        ProjectMemberRole.WORKER.value,
        ProjectMemberRole.ACCEPTER.value,
        ProjectMemberRole.TRAINING_DATA_USER.value,
    ]

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="招待するユーザのuser_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--role", type=str, required=True, choices=role_choices, help="ユーザに割り当てるロール")

    assign_group = parser.add_mutually_exclusive_group(required=True)
    assign_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="招待するプロジェクトのproject_idを指定してください。`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )
    assign_group.add_argument("-org", "--organization", type=str, help="組織配下のすべての進行中のプロジェクトに招待したい場合は、組織名を指定してください。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "invite"
    subcommand_help = "複数のプロジェクトに、ユーザを招待する。"
    description = "複数のプロジェクトに、ユーザを招待する。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
