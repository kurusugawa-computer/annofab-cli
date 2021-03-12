import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

import requests
from annofabapi.models import ProjectMember, ProjectMemberRole, ProjectMemberStatus

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.project_member.put_project_members import PutProjectMembers

logger = logging.getLogger(__name__)


class ChangeProjectMembers(AbstractCommandLineInterface):
    """
    プロジェクトメンバのメンバ情報を更新する。
    """

    def put_project_member(
        self,
        project_id: str,
        user_id: str,
        old_member: ProjectMember,
        member_role: Optional[ProjectMemberRole] = None,
        member_info: Optional[Dict[str, Any]] = None,
    ) -> ProjectMember:
        """
        1人のプロジェクトメンバを変更する。

        Args:
            project_id:
            user_id:
            old_member: 変更前のメンバ情報
            member_role: 変更後のロール。Noneの場合、変更しない。
            member_info: 変更後のメンバ情報。Noneの場合、変更しない。また、対象のキーが存在しない場合は、そのキーに対して変更しない。

        Returns:

        """

        def get_value(key):
            if member_info is None:
                return old_member[key]

            if key not in member_info:
                return old_member[key]

            return member_info[key]

        str_member_role = member_role.value if member_role is not None else old_member["member_role"]

        request_body = {
            "member_status": ProjectMemberStatus.ACTIVE.value,
            "member_role": str_member_role,
            "sampling_inspection_rate": get_value("sampling_inspection_rate"),
            "sampling_acceptance_rate": get_value("sampling_acceptance_rate"),
            "last_updated_datetime": old_member["updated_datetime"],
        }

        updated_project_member = self.service.api.put_project_member(project_id, user_id, request_body=request_body)[0]
        return updated_project_member

    def change_project_members(
        self,
        project_id: str,
        user_id_list,
        member_role: Optional[ProjectMemberRole] = None,
        member_info: Optional[Dict[str, Any]] = None,
    ):
        """
        プロジェクトメンバのメンバ情報を更新する。

        Args:
            project_id: プロジェクトメンバの登録先のプロジェクトのプロジェクトID
            user_id_list: 変更対象のプロジェクトメンバのuser_id
            member_role: メンバに対してして設定するロール。
            member_info: プロジェクトメンバに対して設定するメンバ情報

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        old_project_members = self.service.wrapper.get_all_project_members(project_id)
        project_title = self.facade.get_project_title(project_id)

        count_invite_members = 0
        # プロジェクトメンバを登録
        logger.info(f"{project_title} に、{len(user_id_list)} 件のプロジェクトメンバの情報を変更します。")
        for user_id in user_id_list:
            if user_id == self.service.api.login_user_id:
                logger.warning(f"ユーザ '{user_id}'は自分自身なので、変更できません。")
                continue

            old_member = PutProjectMembers.find_member(old_project_members, user_id)
            if old_member is None:
                logger.warning(f"ユーザ '{user_id}' は、プロジェクトメンバでないため変更できませんでした。")
                continue

            message_for_confirm = f"ユーザ '{user_id}'のプロジェクトメンバ情報を変更しますか？"
            if not self.confirm_processing(message_for_confirm):
                continue

            # メンバを登録
            try:
                self.put_project_member(
                    project_id, user_id, old_member, member_role=member_role, member_info=member_info
                )
                logger.debug(
                    f"user_id = {user_id} のプロジェクトメンバ情報を変更しました。member_role={member_role}, member_info={member_info}"
                )
                count_invite_members += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"プロジェクトメンバの登録に失敗しました。user_id={user_id}")

        logger.info(f"{project_title} に、{count_invite_members} / {len(user_id_list)} 件のプロジェクトメンバを変更しました。")

    def get_all_user_id_list_except_myself(self, project_id: str) -> List[str]:
        """自分自身を除いた、すべてのプロジェクトメンバを取得する"""
        member_list = self.service.wrapper.get_all_project_members(project_id)
        return [e["user_id"] for e in member_list if e["user_id"] != self.service.api.login_user_id]

    @staticmethod
    def validate(args: argparse.Namespace, member_info: Optional[Dict[str, Any]] = None) -> bool:
        COMMON_MESSAGE = "annofabcli project_member change: error:"
        if args.role is None and args.member_info is None:
            print(f"{COMMON_MESSAGE} argument `--role`または`--member_info`のどちらかは、必ず指定してください。", file=sys.stderr)
            return False

        elif member_info is not None and not ChangeProjectMembers.validate_member_info(member_info):
            print(f"{COMMON_MESSAGE} argument --member_info: 有効なキーが１つも指定されていません。", file=sys.stderr)
            return False

        else:
            return True

    @staticmethod
    def validate_member_info(member_info: Dict[str, Any]):
        KEYS = ["sampling_inspection_rate", "sampling_acceptance_rate"]
        return any(k in member_info for k in KEYS)

    def main(self):
        args = self.args
        project_id = args.project_id
        if args.all_user:
            user_id_list = self.get_all_user_id_list_except_myself(project_id)
        else:
            user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        member_info = annofabcli.common.cli.get_json_from_args(args.member_info)
        member_role = ProjectMemberRole(args.role) if args.role is not None else None

        if not self.validate(args, member_info):
            return

        self.change_project_members(
            args.project_id, user_id_list=user_id_list, member_role=member_role, member_info=member_info
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    role_choices = [e.value for e in ProjectMemberRole]

    argument_parser.add_project_id()

    user_group = parser.add_mutually_exclusive_group(required=True)
    user_group.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="変更するプロジェクトメンバのuser_idを指定してください。" "`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )
    user_group.add_argument("--all_user", action="store_true", help="自分以外のすべてのプロジェクトメンバを変更します。")

    parser.add_argument(
        "--role", type=str, choices=role_choices, help="プロジェクトメンバにユーザに割り当てるロールを指定します。指定しない場合は、ロールは変更されません。"
    )

    parser.add_argument(
        "--member_info",
        type=str,
        help="プロジェクトメンバに対して設定するメンバ情報を、JSON形式で指定します。`file://`を先頭に付けると、JSON形式のファイルを指定できます。 "
        "以下のキーが指定可能です。sampling_inspection_rate, sampling_acceptance_rate, "
        "未設定にする場合は、値にnullを指定してください。"
        "詳細は https://annofab.com/docs/api/#operation/putProjectMember を参照ください。 ",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "change"
    subcommand_help = "プロジェクトメンバを変更します。"
    description = "複数のプロジェクトメンバに対して、メンバ情報を変更します。ただし、自分自身は変更できません。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
