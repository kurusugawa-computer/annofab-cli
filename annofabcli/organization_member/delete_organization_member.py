from __future__ import annotations

import argparse
import logging
from collections.abc import Collection
from typing import Any, Optional

import annofabapi
import more_itertools
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


class DeleteOrganizationMemberMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    @staticmethod
    def get_member(organization_member_list: list[dict[str, Any]], user_id: str) -> Optional[dict[str, Any]]:
        return more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)

    def delete_organization_members_from_organization(self, organization_name: str, user_ids: Collection[str]) -> None:
        if not self.facade.contains_any_organization_member_role(organization_name, {OrganizationMemberRole.ADMINISTRATOR, OrganizationMemberRole.OWNER}):
            logger.warning(f"組織'{organization_name}'に所属していないか、組織メンバーを脱退できるロールを持たないため、スキップします。")
            return

        logger.info(f"{len(user_ids)} 件のメンバーを組織'{organization_name}'から脱退させます。")

        member_list = self.service.wrapper.get_all_organization_members(organization_name)

        # プロジェクトメンバを追加/更新する
        success_count = 0
        for user_id in user_ids:
            member = self.get_member(member_list, user_id)
            if member is None:
                logger.warning(f"組織'{organization_name}'に user_id='{user_id}'のメンバーが存在しません。")
                continue

            if not self.confirm_processing(f"組織'{organization_name}'に所属する user_id='{user_id}'のメンバーを脱退させますか？ :: username='{member['username']}'"):
                continue

            try:
                self.service.api.delete_organization_member(organization_name, user_id)
                logger.debug(f"組織'{organization_name}'から user_id='{user_id}'のメンバーを脱退させました。")
                success_count += 1

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"組織'{organization_name}'から user_id='{user_id}'のメンバーを脱退させるのに失敗しました。", exc_info=True)

        logger.info(f"{success_count} / {len(user_ids)} 件のメンバーを組織'{organization_name}'から脱退させました。")

    def delete_organization_members_from_organizations(self, organization_names: list[str], user_ids: Collection[str]) -> None:
        for organization_name in organization_names:
            try:
                self.delete_organization_members_from_organization(organization_name, user_ids)
            except Exception:  # pylint
                logger.warning(f"組織'{organization_name}'からメンバーを脱退させるのに失敗しました。", exc_info=True)


class DeleteOrganizationMember(CommandLine):
    def main(self) -> None:
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)
        organization_name_list = annofabcli.common.cli.get_list_from_args(args.organization)

        main_obj = DeleteOrganizationMemberMain(self.service, all_yes=args.yes)
        main_obj.delete_organization_members_from_organizations(organization_name_list, user_id_list)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteOrganizationMember(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-org",
        "--organization",
        nargs="+",
        required=True,
        type=str,
        help="対象の組織名を指定してます。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="組織から脱退させるメンバーのuser_idを指定します。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "delete"
    subcommand_help = "組織からメンバーを脱退させます。"
    epilog = "組織オーナまたは組織管理者ロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, command_help=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
