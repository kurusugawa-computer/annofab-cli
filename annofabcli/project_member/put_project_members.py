import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import more_itertools
import numpy
import pandas
import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class Member(DataClassJsonMixin):
    """
    登録するプロジェクトメンバ
    """

    user_id: str
    member_role: ProjectMemberRole
    sampling_inspection_rate: Optional[int]
    sampling_acceptance_rate: Optional[int]


class PutProjectMembers(AbstractCommandLineInterface):
    """
    プロジェクトメンバをCSVで登録する。
    """

    @staticmethod
    def find_member(members: List[Dict[str, Any]], user_id: str) -> Optional[Dict[str, Any]]:
        member = more_itertools.first_true(members, default=None, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def member_exists(members: List[Dict[str, Any]], user_id) -> bool:
        return PutProjectMembers.find_member(members, user_id) is not None

    def invite_project_member(self, project_id, member: Member, old_project_members: List[Dict[str, Any]]):
        old_member = self.find_member(old_project_members, member.user_id)
        last_updated_datetime = old_member["updated_datetime"] if old_member is not None else None

        request_body = {
            "member_status": ProjectMemberStatus.ACTIVE.value,
            "member_role": member.member_role.value,
            "sampling_inspection_rate": member.sampling_inspection_rate,
            "sampling_acceptance_rate": member.sampling_acceptance_rate,
            "last_updated_datetime": last_updated_datetime,
        }
        updated_project_member = self.service.api.put_project_member(
            project_id, member.user_id, request_body=request_body
        )[0]
        return updated_project_member

    def delete_project_member(self, project_id, deleted_member: Dict[str, Any]):
        request_body = {
            "member_status": ProjectMemberStatus.INACTIVE.value,
            "member_role": deleted_member["member_role"],
            "last_updated_datetime": deleted_member["updated_datetime"],
        }
        updated_project_member = self.service.api.put_project_member(
            project_id, deleted_member["user_id"], request_body=request_body
        )[0]
        return updated_project_member

    def put_project_members(self, project_id: str, members: List[Member], delete: bool = False):
        """
        プロジェクトメンバを一括で登録する。

        Args:
            project_id: プロジェクトメンバの登録先のプロジェクトのプロジェクトID
            members: 登録するプロジェクトメンバのList
            delete: Trueならば、membersにないメンバを、対象プロジェクトから削除する。

        """

        super().validate_project(project_id, [ProjectMemberRole.OWNER])

        organization_name = self.facade.get_organization_name_from_project_id(project_id)
        organization_members = self.service.wrapper.get_all_organization_members(organization_name)

        old_project_members = self.service.wrapper.get_all_project_members(project_id)
        project_title = self.facade.get_project_title(project_id)

        count_invite_members = 0
        # プロジェクトメンバを登録
        logger.info(f"{project_title} に、{len(members)} 件のプロジェクトメンバを登録します。")
        for member in members:
            if member.user_id == self.service.api.login_user_id:
                logger.debug(f"ユーザ '{member.user_id}'は自分自身なので、登録しません。")
                continue

            if not self.member_exists(organization_members, member.user_id):
                logger.warning(f"ユーザ '{member.user_id}' は、" f"'{organization_name}' 組織の組織メンバでないため、登録できませんでした。")
                continue

            message_for_confirm = (
                f"ユーザ '{member.user_id}'を、{project_title} プロジェクトのメンバに登録しますか？" f"member_role={member.member_role.value}"
            )
            if not self.confirm_processing(message_for_confirm):
                continue

            # メンバを登録
            try:
                self.invite_project_member(project_id, member, old_project_members)
                logger.debug(
                    f"user_id = {member.user_id}, member_role = {member.member_role.value} のユーザをプ" f"ロジェクトメンバに登録しました。"
                )
                count_invite_members += 1

            except requests.exceptions.HTTPError as e:
                logger.warning(e)
                logger.warning(
                    f"プロジェクトメンバの登録に失敗しました。" f"user_id = {member.user_id}, member_role = {member.member_role.value}"
                )

        logger.info(f"{project_title} に、{count_invite_members} / {len(members)} 件のプロジェクトメンバを登録しました。")

        # プロジェクトメンバを削除
        if delete:
            user_id_list = [e.user_id for e in members]
            # 自分自身は削除しないようにする
            deleted_members = [
                e
                for e in old_project_members
                if (e["user_id"] not in user_id_list and e["user_id"] != self.service.api.login_user_id)
            ]

            count_delete_members = 0
            logger.info(f"{project_title} から、{len(deleted_members)} 件のプロジェクトメンバを削除します。")
            for deleted_member in deleted_members:
                message_for_confirm = f"ユーザ '{deleted_member['user_id']}'を、" f"{project_title} のプロジェクトメンバから削除しますか？"
                if not self.confirm_processing(message_for_confirm):
                    continue

                try:
                    self.delete_project_member(project_id, deleted_member)
                    logger.debug(f"ユーザ '{deleted_member['user_id']}' をプロジェクトメンバから削除しました。")
                    count_delete_members += 1
                except requests.exceptions.HTTPError as e:
                    logger.warning(e)
                    logger.warning(f"プロジェクトメンバの削除に失敗しました。user_id = '{deleted_member['user_id']}' ")

            logger.info(f"{project_title} から {count_delete_members} / {len(deleted_members)} 件の" f"プロジェクトメンバを削除しました。")

    @staticmethod
    def get_members_from_csv(csv_path: Path) -> List[Member]:
        def create_member(e):
            return Member(
                user_id=e.user_id,
                member_role=ProjectMemberRole(e.member_role),
                sampling_inspection_rate=e.sampling_inspection_rate,
                sampling_acceptance_rate=e.sampling_acceptance_rate,
            )

        df = pandas.read_csv(
            str(csv_path),
            sep=",",
            header=None,
            names=("user_id", "member_role", "sampling_inspection_rate", "sampling_acceptance_rate"),
            # IDは必ず文字列として読み込むようにする
            dtype={"user_id": str},
        ).replace({numpy.nan: None})
        members = [create_member(e) for e in df.itertuples()]
        return members

    def main(self):
        args = self.args
        members = self.get_members_from_csv(Path(args.csv))
        self.put_project_members(args.project_id, members=members, delete=args.delete)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help=(
            "プロジェクトメンバが記載されたCVファイルのパスを指定してください。"
            "CSVのフォーマットは、「1列目:user_id(required), 2列目:member_role(required), "
            "3列目:sampling_inspection_rate, 4列目:sampling_acceptance_rate, ヘッダ行なし, カンマ区切り」です。"
            "member_roleは ``owner``, ``worker``, ``accepter``, ``training_data_user`` のいずれかです。"
            "sampling_inspection_rate, sampling_acceptance_rate を省略した場合は未設定になります。"
            "ただし自分自身は登録しません。"
        ),
    )

    parser.add_argument("--delete", action="store_true", help="CSVファイルに記載されていないプロジェクトメンバを削除します。ただし自分自身は削除しません。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "put"
    subcommand_help = "プロジェクトメンバを登録する。"
    description = "プロジェクトメンバを登録する。"
    epilog = "オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
