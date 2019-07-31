import argparse
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import annofabapi
from annofabapi.models import ProjectMember, ProjectMemberRole

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

        super().validate_project(src_project_id, roles=None)
        super().validate_project(dest_project_id, roles=[ProjectMemberRole.OWNER])

    def copy_project_members(self, src_project_id: str, dest_project_id: str, delete_dest: bool = False):
        """
        プロジェクトメンバを、別のプロジェクトにコピーする。

        Note:
            誤って実行しないようにすること

        Args:
            src_project_id: コピー元のproject_id
            dest_project_id: コピー先のproject_id
            delete_dest: Trueならばコピー先にしか存在しないプロジェクトメンバを削除する。

        Returns:
            `putProjectMember` APIのContentのList

        """

        self.validate_projects(src_project_id, dest_project_id)

        src_project_members = self.service.wrapper.get_all_project_members(src_project_id)
        dest_project_members = self.service.wrapper.get_all_project_members(dest_project_id)

        # 追加対象のプロジェクトメンバ
        dest_account_ids = [e["account_id"] for e in dest_project_members]
        added_members = [e for e in src_project_members if e["account_id"] not in dest_account_ids]

        for member in added_members:
            logger.info(f"{self.dest_project_title} プロジェクトに追加するメンバ: {member['user_id']} , {member['username']}")

        # 更新対象のプロジェクトメンバ
        updated_members = src_project_members
        deleted_dest_members: List[ProjectMember] = []

        if delete_dest:
            # コピー先にしかいないメンバを削除する
            src_account_ids = [e["account_id"] for e in src_project_members]
            deleted_dest_members = [e for e in dest_project_members if e["account_id"] not in src_account_ids]

            def to_inactive(arg_member):
                arg_member['member_status'] = 'inactive'
                return arg_member

            deleted_dest_members = list(map(to_inactive, deleted_dest_members))
            for member in deleted_dest_members:
                logger.info(f"{self.dest_project_title} プロジェクトから削除するメンバ: {member['user_id']} , {member['username']}")

            updated_members = updated_members + deleted_dest_members

        if self.confirm_processing(f"{self.src_project_title} プロジェクトのメンバを、"
                                   f"{self.dest_project_title} にコピーしますか？"
                                   f"追加対象: {len(added_members)} 件, 削除対象: {len(deleted_dest_members)} 件"):
            self.service.wrapper.put_project_members(dest_project_id, updated_members)

    def main(self):
        args = self.args
        self.copy_project_members(args.src_project_id, args.dest_project_id, delete_dest=args.delete_dest)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    CopyProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('src_project_id', type=str, help='コピー元のプロジェクトのproject_id')
    parser.add_argument('dest_project_id', type=str, help='コピー先のプロジェクトのproject_id')

    parser.add_argument('--delete_dest', action='store_true', help='コピー先のプロジェクトにしか存在しないプロジェクトメンバを削除します。')

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "プロジェクトメンバをコピーする。"
    description = ("プロジェクトメンバをコピーする。")
    epilog = "コピー先のプロジェクトに対して、オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
