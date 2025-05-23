import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import more_itertools
import pandas
import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


@dataclass
class Member(DataClassJsonMixin):
    """
    登録するプロジェクトメンバ
    """

    user_id: str
    member_role: ProjectMemberRole
    sampling_inspection_rate: Optional[int] = None
    sampling_acceptance_rate: Optional[int] = None


class PutProjectMembers(CommandLine):
    """
    プロジェクトメンバをCSVで登録する。
    """

    @staticmethod
    def find_member(members: list[dict[str, Any]], user_id: str) -> Optional[dict[str, Any]]:
        member = more_itertools.first_true(members, default=None, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def member_exists(members: list[dict[str, Any]], user_id: str) -> bool:
        return PutProjectMembers.find_member(members, user_id) is not None

    def invite_project_member(self, project_id: str, member: Member, old_project_members: list[dict[str, Any]]) -> dict[str, Any]:
        old_member = self.find_member(old_project_members, member.user_id)
        last_updated_datetime = old_member["updated_datetime"] if old_member is not None else None

        request_body = {
            "member_status": ProjectMemberStatus.ACTIVE.value,
            "member_role": member.member_role.value,
            "sampling_inspection_rate": member.sampling_inspection_rate,
            "sampling_acceptance_rate": member.sampling_acceptance_rate,
            "last_updated_datetime": last_updated_datetime,
        }
        updated_project_member = self.service.api.put_project_member(project_id, member.user_id, request_body=request_body)[0]
        return updated_project_member

    def delete_project_member(self, project_id: str, deleted_member: dict[str, Any]) -> dict[str, Any]:
        request_body = {
            "member_status": ProjectMemberStatus.INACTIVE.value,
            "member_role": deleted_member["member_role"],
            "last_updated_datetime": deleted_member["updated_datetime"],
        }
        updated_project_member = self.service.api.put_project_member(project_id, deleted_member["user_id"], request_body=request_body)[0]
        return updated_project_member

    def put_project_members(self, project_id: str, members: list[Member], *, delete: bool = False) -> None:
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
        logger.info(f"プロジェクト '{project_title}' に、{len(members)} 件のプロジェクトメンバを登録します。")
        for member in members:
            if member.user_id == self.service.api.login_user_id:
                logger.debug(f"ユーザ '{member.user_id}'は自分自身なので、登録しません。")
                continue

            if not self.member_exists(organization_members, member.user_id):
                logger.warning(f"ユーザ '{member.user_id}' は、'{organization_name}' 組織の組織メンバでないため、登録できませんでした。")
                continue

            message_for_confirm = f"ユーザ '{member.user_id}'を、プロジェクト'{project_title}'のメンバーに登録しますか？ member_role='{member.member_role.value}'"
            if not self.confirm_processing(message_for_confirm):
                continue

            # メンバを登録
            try:
                self.invite_project_member(project_id, member, old_project_members)
                logger.debug(f"user_id = '{member.user_id}', member_role = '{member.member_role.value}' のユーザをプロジェクトメンバに登録しました。")
                count_invite_members += 1

            except requests.exceptions.HTTPError:
                logger.warning(f"プロジェクトメンバの登録に失敗しました。user_id = '{member.user_id}', member_role = '{member.member_role.value}'", exc_info=True)

        logger.info(f"プロジェクト'{project_title}' に、{count_invite_members} / {len(members)} 件のプロジェクトメンバを登録しました。")

        # プロジェクトメンバを削除
        if delete:
            user_id_list = [e.user_id for e in members]
            # 自分自身は削除しないようにする
            deleted_members = [e for e in old_project_members if (e["user_id"] not in user_id_list and e["user_id"] != self.service.api.login_user_id)]

            count_delete_members = 0
            logger.info(f"プロジェクト '{project_title}' から、{len(deleted_members)} 件のプロジェクトメンバを削除します。")
            for deleted_member in deleted_members:
                message_for_confirm = f"ユーザ '{deleted_member['user_id']}'を、{project_title} のプロジェクトメンバから削除しますか？"
                if not self.confirm_processing(message_for_confirm):
                    continue

                try:
                    self.delete_project_member(project_id, deleted_member)
                    logger.debug(f"ユーザ '{deleted_member['user_id']}' をプロジェクトメンバから削除しました。")
                    count_delete_members += 1
                except requests.exceptions.HTTPError:
                    logger.warning(f"プロジェクトメンバの削除に失敗しました。user_id = '{deleted_member['user_id']}' ", exc_info=True)

            logger.info(f"プロジェクト '{project_title}' から {count_delete_members} / {len(deleted_members)} 件のプロジェクトメンバを削除しました。")

    @staticmethod
    def get_members_from_csv(csv_path: Path) -> list[Member]:
        df = pandas.read_csv(
            csv_path,
            dtype={"user_id": "string", "member_role": "string", "sampling_inspection_rate": "Int64", "sampling_acceptance_rate": "Int64"},
        )
        members = [Member.from_dict(e) for e in df.to_dict("records")]
        return members

    def main(self) -> None:
        args = self.args
        members = self.get_members_from_csv(Path(args.csv))
        self.put_project_members(args.project_id, members=members, delete=args.delete)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutProjectMembers(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help=(
            "プロジェクトメンバが記載されたCSVファイルのパスを指定してください。"
            "CSVのフォーマットは、ヘッダあり、カンマ区切りです。\n"
            " * user_id (required)\n"
            " * member_role (required)\n"
            " * sampling_inspection_rate\n"
            " * sampling_acceptance_rate\n"
            "member_roleには ``owner``, ``worker``, ``accepter``, ``training_data_user`` のいずれかを指定します。\n"
            "自分自身は登録できません。"
        ),
    )

    parser.add_argument("--delete", action="store_true", help="CSVファイルに記載されていないプロジェクトメンバを削除します。ただし自分自身は削除しません。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put"
    subcommand_help = "プロジェクトメンバを登録します。"
    epilog = "オーナーロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
