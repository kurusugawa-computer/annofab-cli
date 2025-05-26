import argparse
import logging
from collections.abc import Collection
from typing import Optional

import annofabapi
from annofabapi.models import OrganizationMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class InviteOrganizationMemberMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    def invite_members_to_organization(self, organization_name: str, user_ids: Collection[str], role: str) -> None:
        if not self.facade.contains_any_organization_member_role(organization_name, {OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER}):
            logger.warning(f"組織'{organization_name}'に所属していないか、組織メンバーを招待できるロールを持たないため、スキップします。")
            return

        logger.info(f"{len(user_ids)} 件のメンバーを組織'{organization_name}'に招待して、ロール'{role}'を付与します。")

        organization_member_list = self.service.wrapper.get_all_organization_members(organization_name)
        all_user_ids = {e["user_id"] for e in organization_member_list}

        # プロジェクトメンバを追加/更新する
        success_count = 0
        for user_id in user_ids:
            if user_id in all_user_ids:
                logger.warning(f"user_id='{user_id}'のメンバーは、すでに組織'{organization_name}'に存在しているため、スキップします。")
                continue

            if not self.confirm_processing(f"user_id='{user_id}'のメンバーを組織'{organization_name}'に招待して、ロール'{role}'を付与しますか？"):
                continue

            try:
                self.service.api.invite_organization_member(organization_name, user_id, request_body={"role": role})
                logger.debug(f"user_id='{user_id}'のメンバーを組織'{organization_name}'に招待しました。")
                success_count += 1

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"user_id='{user_id}'のメンバーを組織'{organization_name}'に招待するのに失敗しました。", exc_info=True)

        logger.info(f"{success_count} / {len(user_ids)} 件のメンバーを組織'{organization_name}'に招待しました。")

    def invite_members_to_organizations(self, organization_names: list[str], user_ids: Collection[str], role: str) -> None:
        for organization_name in organization_names:
            try:
                self.invite_members_to_organization(organization_name, user_ids, role)
            except Exception:  # pylint
                logger.warning(f"組織'{organization_name}'にメンバーを招待するのに失敗しました。", exc_info=True)


class InviteOrganizationMember(CommandLine):
    def main(self) -> None:
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)
        organization_name_list = annofabcli.common.cli.get_list_from_args(args.organization)

        main_obj = InviteOrganizationMemberMain(self.service, all_yes=args.yes)
        main_obj.invite_members_to_organizations(organization_name_list, user_id_list, role=args.role)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    InviteOrganizationMember(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-org", "--organization", nargs="+", required=True, type=str, help="招待先の組織名を指定してください。")

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="組織に招待するメンバーのuser_idを指定してます。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    role_choices = [e.value for e in OrganizationMemberRole]
    parser.add_argument(
        "--role",
        type=str,
        choices=role_choices,
        required=True,
        help="招待するメンバーに割り当てるロールを指定してください。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "invite"
    subcommand_help = "組織にメンバーを招待します。"
    epilog = "組織オーナまたは組織管理者ロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, command_help=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
