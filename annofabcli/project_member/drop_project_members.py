import argparse
import logging
from typing import Optional

import annofabapi
import requests
from annofabapi.models import ProjectMemberStatus
from more_itertools import first_true

import annofabcli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DropProjectMembersMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def drop_project_members(self, project_id: str, user_id_list: list[str]):  # noqa: ANN201
        """
        複数ユーザをプロジェクトメンバから脱退させる

        Args:
            project_id:
            user_id_list:

        """
        dest_project_members = self.service.wrapper.get_all_project_members(project_id)

        def get_project_member(user_id: str):  # noqa: ANN202
            return first_true(dest_project_members, pred=lambda e: e["user_id"] == user_id)

        project_title = self.facade.get_project_title(project_id)

        # プロジェクトメンバを追加/更新する
        for user_id in user_id_list:
            dest_member = get_project_member(user_id)
            if dest_member is None or dest_member["member_status"] == ProjectMemberStatus.INACTIVE.value:
                logger.debug(f"{project_title}({project_id}) のプロジェクトメンバに、{user_id} は存在しないので、スキップします。")
                continue

            request_body = {
                "member_status": ProjectMemberStatus.INACTIVE.value,
                "member_role": dest_member["member_role"],
                "last_updated_datetime": dest_member["updated_datetime"],
            }
            try:
                self.service.api.put_project_member(project_id, user_id, request_body=request_body)
                logger.debug(f"プロジェクト'{project_title}'(project_id='{project_id}') から、user_id='{user_id}'のユーザーを脱退させました。")
            except requests.HTTPError:
                logger.warning(f"プロジェクト'{project_title}'(project_id='{project_id}') から、user_id='{user_id}'のユーザーを脱退させられませんでした。")

    def drop_role_with_organization(self, organization_name: str, user_id_list: list[str]):  # noqa: ANN201
        projects = self.service.wrapper.get_all_projects_of_organization(organization_name, query_params={"account_id": self.service.api.account_id})

        project_id_list = [e["project_id"] for e in projects]
        self.drop_role_with_project_id(project_id_list, user_id_list=user_id_list)

    def drop_role_with_project_id(self, project_id_list: list[str], user_id_list: list[str]):  # noqa: ANN201
        for project_id in project_id_list:
            try:
                if not self.facade.my_role_is_owner(project_id):
                    logger.warning(f"オーナではないため、プロジェクトメンバを脱退させられません。 :: project_id='{project_id}'")
                    continue

                self.drop_project_members(project_id, user_id_list)

            except requests.HTTPError:
                logger.warning(f"project_id='{project_id}' のプロジェクトメンバからユーザを脱退させられませんでした。", exc_info=True)


class DropProjectMembers(CommandLine):
    """
    ユーザをプロジェクトから削除する
    """

    def main(self) -> None:
        args = self.args
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = DropProjectMembersMain(self.service)
        if args.organization is not None:
            main_obj.drop_role_with_organization(args.organization, user_id_list)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            main_obj.drop_role_with_project_id(project_id_list, user_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DropProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="脱退させるユーザのuser_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    drop_group = parser.add_mutually_exclusive_group(required=True)
    drop_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="脱退させるプロジェクトのproject_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    drop_group.add_argument(
        "-org",
        "--organization",
        type=str,
        help="組織名を指定すると、組織配下のすべてのプロジェクト（自分が所属している）から、ユーザを脱退させます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "複数のプロジェクトから、ユーザを脱退させます。"
    description = "複数のプロジェクトから、ユーザを脱退させます。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
