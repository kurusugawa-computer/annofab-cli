import argparse
import logging
from typing import List, Optional

import annofabapi
import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from more_itertools import first_true

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class InviteProjectMemberMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def invite_project_members(self, project_id: str, user_id_list: List[str], member_role: ProjectMemberRole):
        """
        プロジェクトに、複数ユーザをプロジェクトメンバに追加する

        Args:
            project_id:
            user_id_list:
            member_role:

        Returns:

        """
        dest_project_members = self.service.wrapper.get_all_project_members(project_id)

        def get_project_member(user_id: str):
            return first_true(dest_project_members, pred=lambda e: e["user_id"] == user_id)

        project_title = self.facade.get_project_title(project_id)

        # プロジェクトメンバを追加/更新する
        for user_id in user_id_list:
            dest_member = get_project_member(user_id)
            if dest_member is not None:
                last_updated_datetime = dest_member["updated_datetime"]
            else:
                last_updated_datetime = None

            request_body = {
                "member_status": ProjectMemberStatus.ACTIVE.value,
                "member_role": member_role.value,
                "last_updated_datetime": last_updated_datetime,
            }
            try:
                self.service.api.put_project_member(project_id, user_id, request_body=request_body)
                logger.debug(f"{project_title}({project_id}) のプロジェクトメンバに、{user_id} を {member_role.value} ロールで追加しました。")
            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(
                    f"{project_title}({project_id}) のプロジェクトメンバに、{user_id} を {member_role.value} ロールで追加できませんでした。"
                )

    def assign_role_with_organization(
        self, organization_name: str, user_id_list: List[str], member_role: ProjectMemberRole
    ):
        projects = self.service.wrapper.get_all_projects_of_organization(
            organization_name, query_params={"account_id": self.service.api.account_id}
        )
        project_id_list = [e["project_id"] for e in projects]
        self.assign_role_with_project_id(project_id_list, user_id_list=user_id_list, member_role=member_role)

    def assign_role_with_project_id(
        self, project_id_list: List[str], user_id_list: List[str], member_role: ProjectMemberRole
    ):
        for project_id in project_id_list:
            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(f"オーナではないため、プロジェクトメンバを招待できません。" f"project_id = {project_id}")
                    continue

                self.invite_project_members(project_id, user_id_list, member_role)

            except requests.HTTPError as e:
                logger.warning(e)
                logger.warning(f"project_id={project_id} のプロジェクトメンバにユーザを招待できませんでした。")


class InviteUser(AbstractCommandLineInterface):
    """
    ユーザをプロジェクトに招待する
    """

    def main(self):
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = InviteProjectMemberMain(self.service)
        if args.organization is not None:
            main_obj.assign_role_with_organization(args.organization, user_id_list, ProjectMemberRole(args.role))

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            main_obj.assign_role_with_project_id(project_id_list, user_id_list, ProjectMemberRole(args.role))


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
        help="招待するユーザのuser_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--role", type=str, required=True, choices=role_choices, help="ユーザに割り当てるロール")

    assign_group = parser.add_mutually_exclusive_group(required=True)
    assign_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="招待するプロジェクトのproject_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )
    assign_group.add_argument("-org", "--organization", type=str, help="組織名を指定すると、組織配下のすべてのプロジェクト（自分が所属している）に招待します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "invite"
    subcommand_help = "複数のプロジェクトに、ユーザを招待します。"
    description = "複数のプロジェクトに、ユーザを招待します。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
