import argparse
import logging
from typing import Any, Dict, List, Optional

import annofabapi
from annofabapi.models import OrganizationMember, ProjectMember, ProjectMemberRole

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class CopyProjectMembers(AbstractCommandLineInterface):
    """
    プロジェクトメンバをコピーする
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)

        src_project_id = args.src_project_id
        dest_project_id = args.dest_project_id
        project_title1 = self.facade.get_project_title(src_project_id)
        project_title2 = self.facade.get_project_title(dest_project_id)

        self.src_project_title = project_title1
        self.dest_project_title = project_title2

    def validate_projects(self, src_project_id: str, dest_project_id: str):
        """
        適切なRoleが付与されているかを確認する。

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。

        """

        super().validate_project(src_project_id, project_member_roles=None)
        super().validate_project(dest_project_id, project_member_roles=[ProjectMemberRole.OWNER])

    def get_organization_members_from_project_id(self, project_id: str) -> List[OrganizationMember]:
        organization_name = self.facade.get_organization_name_from_project_id(project_id)
        return self.service.wrapper.get_all_organization_members(organization_name)

    @staticmethod
    def find_member(members: List[Dict[str, Any]], account_id: str) -> Optional[Dict[str, Any]]:
        for m in members:
            if m["account_id"] == account_id:
                return m

        return None

    def put_project_members(self, project_id, project_members: List[Dict[str, Any]]) -> List[ProjectMember]:
        """
        複数のプロジェクトメンバを追加/更新/削除する.

        Args:
            project_id: プロジェクトID
            project_members: 追加/更新するメンバのList. `user_id` , `member_status` , `member_role` をKeyに持つこと

        Returns:
            `putProjectMember` APIのContentのList

        """
        # 追加/更新前のプロジェクトメンバ
        dest_project_members = self.service.wrapper.get_all_project_members(project_id)

        updated_project_members = []
        # プロジェクトメンバを追加/更新する
        for member in project_members:
            dest_member = [e for e in dest_project_members if e["user_id"] == member["user_id"]]
            last_updated_datetime = dest_member[0]["updated_datetime"] if len(dest_member) > 0 else None

            request_body = {
                "member_status": member["member_status"],
                "member_role": member["member_role"],
                "sampling_inspection_rate": member.get("sampling_inspection_rate"),
                "sampling_acceptance_rate": member.get("sampling_acceptance_rate"),
                "last_updated_datetime": last_updated_datetime,
            }
            updated_project_member = self.service.api.put_project_member(
                project_id, member["user_id"], request_body=request_body
            )[0]
            updated_project_members.append(updated_project_member)

            command_name = "追加" if last_updated_datetime is None else "更新"
            logger.debug(
                "プロジェクトメンバの'%s' 完了." " project_id=%s, user_id=%s, ",
                command_name,
                project_id,
                member["user_id"],
            )

        return updated_project_members

    def copy_project_members(self, src_project_id: str, dest_project_id: str, delete_dest: bool = False):
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: コピー先のproject_id
            delete_dest: Trueならばコピー先にしか存在しないプロジェクトメンバを削除する。

        """

        self.validate_projects(src_project_id, dest_project_id)

        src_project_members = self.service.wrapper.get_all_project_members(src_project_id)
        src_organization_members = self.get_organization_members_from_project_id(src_project_id)
        # 組織外のメンバが含まれている可能性があるので、除去する
        src_project_members = [
            e for e in src_project_members if self.find_member(src_organization_members, e["account_id"]) is not None
        ]

        dest_project_members = self.service.wrapper.get_all_project_members(dest_project_id)
        dest_organization_members = self.get_organization_members_from_project_id(dest_project_id)
        dest_organization_name = self.facade.get_organization_name_from_project_id(dest_project_id)

        # 追加対象のプロジェクトメンバ
        added_members = []
        for member in src_project_members:
            account_id = member["account_id"]
            if self.find_member(dest_organization_members, account_id) is None:
                # コピー先の組織メンバでないので、コピーしない
                logger.debug(
                    f"コピーしないメンバ: {member['user_id']} , {member['username']} : "
                    f"(コピー先の所属組織 {dest_organization_name} の組織メンバでないため)"
                )
                continue

            added_members.append(member)

        for member in added_members:
            logger.debug(f"{self.dest_project_title} プロジェクトに追加/更新するメンバ: {member['user_id']} , {member['username']}")

        # 更新対象のプロジェクトメンバ
        updated_members = added_members
        deleted_dest_members: List[ProjectMember] = []

        if delete_dest:
            # コピー先にしかいないメンバを削除する
            src_account_ids = [e["account_id"] for e in src_project_members]
            deleted_dest_members = [e for e in dest_project_members if e["account_id"] not in src_account_ids]

            def to_inactive(arg_member):
                arg_member["member_status"] = "inactive"
                return arg_member

            deleted_dest_members = list(map(to_inactive, deleted_dest_members))
            for member in deleted_dest_members:
                logger.debug(f"{self.dest_project_title} プロジェクトから削除するメンバ: {member['user_id']} , {member['username']}")

            updated_members = updated_members + deleted_dest_members

        if len(added_members) > 0:
            if self.confirm_processing(
                f"'{self.src_project_title}' のプロジェクトのメンバを、"
                f"'{self.dest_project_title}' にコピーしますか？"
                f"追加対象: {len(added_members)} 件, 削除対象: {len(deleted_dest_members)} 件"
            ):
                self.put_project_members(dest_project_id, updated_members)
        else:
            logger.info(f"{self.dest_project_title}のプロジェクトメンバに追加/更新はありません。")

    def main(self):
        args = self.args
        self.copy_project_members(args.src_project_id, args.dest_project_id, delete_dest=args.delete_dest)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("src_project_id", type=str, help="コピー元のプロジェクトのproject_id")
    parser.add_argument("dest_project_id", type=str, help="コピー先のプロジェクトのproject_id")

    parser.add_argument("--delete_dest", action="store_true", help="コピー先のプロジェクトにしか存在しないプロジェクトメンバを削除します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトメンバをコピーする。"
    description = "プロジェクトメンバをコピーする。"
    epilog = "コピー先のプロジェクトに対して、オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
