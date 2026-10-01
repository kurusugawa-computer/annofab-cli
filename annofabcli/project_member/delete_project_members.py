import argparse
import logging
from typing import Any

import annofabapi
import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from more_itertools import first_true

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DeleteProjectMembersMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, *, all_yes: bool = False) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    def delete_project_members(self, project_id: str, user_id_list: list[str]) -> None:
        """
        複数ユーザをプロジェクトメンバから脱退させる

        Args:
            project_id:
            user_id_list:

        """
        dest_project_members = self.service.wrapper.get_all_project_members(project_id)

        def get_project_member(user_id: str) -> dict[str, Any] | None:
            return first_true(dest_project_members, pred=lambda e: e["user_id"] == user_id)

        project_title = self.facade.get_project_title(project_id)

        success_count = 0
        skipped_count = 0
        failure_count = 0
        logger.info(f"プロジェクト'{project_title}'から、{len(user_id_list)} 件のユーザを脱退させます。project_id='{project_id}'")
        for index, user_id in enumerate(user_id_list, start=1):
            logger.debug(f"{index} / {len(user_id_list)} 件目: user_id='{user_id}'")
            dest_member = get_project_member(user_id)
            if dest_member is None or dest_member["member_status"] == ProjectMemberStatus.INACTIVE.value:
                logger.warning(f"{project_title}({project_id}) の有効なプロジェクトメンバに、user_id='{user_id}' は存在しないためスキップします。")
                skipped_count += 1
                continue

            if not self.confirm_processing(f"プロジェクト'{project_title}'(project_id='{project_id}')から、user_id='{user_id}'のユーザーを脱退させますか？"):
                skipped_count += 1
                continue

            request_body = {
                "member_status": ProjectMemberStatus.INACTIVE.value,
                "member_role": dest_member["member_role"],
                "last_updated_datetime": dest_member["updated_datetime"],
            }
            try:
                self.service.api.put_project_member(project_id, user_id, request_body=request_body)
                logger.debug(f"プロジェクト'{project_title}'(project_id='{project_id}') から、user_id='{user_id}'のユーザーを脱退させました。")
                success_count += 1
            except requests.HTTPError:
                logger.warning(f"プロジェクト'{project_title}'(project_id='{project_id}') から、user_id='{user_id}'のユーザーを脱退させられませんでした。", exc_info=True)
                failure_count += 1

        logger.info(f"プロジェクト'{project_title}'からの脱退処理が完了しました。成功: {success_count} 件、スキップ: {skipped_count} 件、失敗: {failure_count} 件。project_id='{project_id}'")

    def delete_members_from_organization_projects(self, organization_name: str, user_id_list: list[str]) -> None:
        projects = self.service.wrapper.get_all_projects_of_organization(organization_name, query_params={"account_id": self.service.api.account_id})

        project_id_list = [e["project_id"] for e in projects]
        self.delete_members_from_projects(project_id_list, user_id_list=user_id_list)

    def delete_members_from_projects(self, project_id_list: list[str], user_id_list: list[str]) -> None:
        for project_id in project_id_list:
            try:
                if not self.facade.contains_any_project_member_role(project_id, [ProjectMemberRole.OWNER]):
                    logger.warning(f"オーナではないため、プロジェクトメンバを脱退させられません。 :: project_id='{project_id}'")
                    continue

                self.delete_project_members(project_id, user_id_list)

            except requests.HTTPError:
                logger.warning(f"project_id='{project_id}' のプロジェクトメンバからユーザを脱退させられませんでした。", exc_info=True)


class DeleteProjectMembers(CommandLine):
    """
    ユーザをプロジェクトメンバから脱退させる
    """

    def main(self) -> None:
        args = self.args
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = DeleteProjectMembersMain(self.service, all_yes=args.yes)
        if args.organization is not None:
            main_obj.delete_members_from_organization_projects(args.organization, user_id_list)

        elif args.project_id is not None:
            project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)
            main_obj.delete_members_from_projects(project_id_list, user_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteProjectMembers(service, facade, args).main()


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


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "複数のプロジェクトから、ユーザを脱退させます。"
    description = "複数のプロジェクトから、ユーザを脱退させます。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
