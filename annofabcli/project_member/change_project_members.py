import argparse
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from dataclasses_json import dataclass_json

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.project_member.put_project_members import PutProjectMembers

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class MemberInfo:
    """
    プロジェクトメンバに対して変更できる情報
    """
    member_role: Optional[ProjectMemberRole] = None
    sampling_inspection_rate: Optional[int] = None
    sampling_acceptance_rate: Optional[int] = None


class ChangeProjectMembers(AbstractCommandLineInterface):
    """
    プロジェクトメンバのメンバ情報を更新する。
    """
    def put_project_member(self, project_id, user_id: str, member_info: MemberInfo,
                           old_member: Dict[str, Any]) -> Dict[str, Any]:

        def get_value(target, default):
            return target if target is not None else default

        request_body = {
            "member_status": ProjectMemberStatus.ACTIVE.value,
            "member_role": get_value(member_info.member_role.value, old_member["member_role"]),
            "sampling_inspection_rate": get_value(member_info.sampling_inspection_rate, old_member["sampling_inspection_rate"]),
            "sampling_acceptance_rate": get_value(member_info.sampling_acceptance_rate, old_member["sampling_acceptance_rate"]),
            "last_updated_datetime": old_member["updated_datetime"],
        }

        updated_project_member = self.service.api.put_project_member(project_id, user_id, request_body=request_body)[0]
        return updated_project_member

    def change_project_members(self, project_id: str, user_id_list, member_info: MemberInfo):
        """
        プロジェクトメンバのメンバ情報を更新する。

        Args:
            project_id: プロジェクトメンバの登録先のプロジェクトのプロジェクトID
            user_id_list: 変更対象のプロジェクトメンバのuser_id
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

            message_for_confirm = (f"ユーザ '{user_id}'のプロジェクトメンバ情報を変更しますか？")
            if not self.confirm_processing(message_for_confirm):
                continue

            # メンバを登録
            try:
                self.put_project_member(project_id, user_id, member_info=member_info,
                                        old_member=old_member)
                logger.debug(f"user_id = {user_id} のプロジェクトメンバ情報を変更しました。")
                count_invite_members += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(f"プロジェクトメンバの登録に失敗しました。user_id={user_id}")

        logger.info(f"{project_title} に、{count_invite_members} / {len(user_id_list)} 件のプロジェクトメンバを変更しました。")

    def get_all_user_id_list_except_myself(self, project_id) -> List[str]:
        """自分自身を除いた、すべてのプロジェクトメンバを取得する"""
        member_list = self.service.wrapper.get_all_project_members(project_id)
        return [e["user_id"] for e in member_list if (e['user_id'] != self.service.api.login_user_id)]

    def main(self):
        args = self.args
        project_id = args.project_id
        if args.all_user:
            user_id_list = self.get_all_user_id_list_except_myself(project_id)
        else:
            user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        # TODO validation
        member_info = MemberInfo.from_dict(annofabcli.common.cli.get_json_from_args(args.member_info))

        self.change_project_members(args.project_id, user_id_list=user_id_list, member_info=member_info)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    ChangeProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    user_group = parser.add_mutually_exclusive_group(required=True)
    user_group.add_argument('-u', '--user_id', type=str, nargs='+', help='変更するプロジェクトメンバのuser_idを指定してください。'
                            '`file://`を先頭に付けると、一覧が記載されたファイルを指定できます。')
    user_group.add_argument('--all_user', action='store_true', help='自分以外のすべてのプロジェクトメンバを変更します。')

    parser.add_argument(
        '--member_info', type=str, required=True,
        help="プロジェクトメンバに対して設定するメンバ情報を、JSON形式で指定します。`file://`を先頭に付けると、JSON形式のファイルを指定できます。 "
        "以下のキーが指定可能です。member_role, sampling_inspection_rate, sampling_acceptance_rate, "
        "詳細は https://annofab.com/docs/api/#operation/putProjectMember を参照ください。 ")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "change"
    subcommand_help = "プロジェクトメンバを変更します。"
    description = ("複数のプロジェクトメンバに対して、メンバ情報を変更します。ただし、自分自身は変更できません。")
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
