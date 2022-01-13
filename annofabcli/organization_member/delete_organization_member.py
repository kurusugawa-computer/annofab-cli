from __future__ import annotations

import argparse
import logging
from typing import Any, Collection, Optional

import annofabapi
import more_itertools

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)


class DeleteOrganizationMemberMain(AbstractCommandLineWithConfirmInterface):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool = False,
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    @staticmethod
    def get_member(organization_member_list: list[dict[str, Any]], user_id: str) -> Optional[dict[str, Any]]:
        return more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)

    def main(self, organization_name: str, user_ids: Collection[str]):
        logger.info(f"{len(user_ids)} 件のユーザを組織'{organization_name}'から脱退させます。")

        member_list = self.service.wrapper.get_all_organization_members(organization_name)

        # プロジェクトメンバを追加/更新する
        success_count = 0
        for user_id in user_ids:
            member = self.get_member(member_list, user_id)
            if member is None:
                logger.warning(f"組織メンバにuser_id='{user_id}'のユーザが存在しません。")
                continue

            if not self.confirm_processing(
                f"user_id='{user_id}'のユーザを組織から脱退させますか？ :: username='{member['username']}', role='{member['role']}'"
            ):
                continue

            logger.debug(
                f"user_id='{user_id}'のユーザを組織から脱退させます。 :: username='{member['username']}', role='{member['role']}'"
            )
            try:
                self.service.api.delete_organization_member(organization_name, user_id)
                logger.debug(f"user_id='{user_id}'のユーザを組織'{organization_name}'から脱退させました。")
                success_count += 1

            except Exception:  # pylint: disable=broad-except
                logger.warning(f"user_id='{user_id}'のユーザを組織'{organization_name}'から脱退させるのに失敗しました。", exc_info=True)

        logger.info(f"{success_count} / {len(user_ids)} 件のユーザを組織'{organization_name}'から脱退させました。")


class DeleteOrganizationMember(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = DeleteOrganizationMemberMain(self.service, all_yes=args.yes)
        main_obj.main(organization_name=args.organization, user_ids=user_id_list)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DeleteOrganizationMember(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("-org", "--organization", required=True, type=str, help="対象の組織の組織名を指定してください。")

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="組織から脱退させるユーザのuser_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "delete"
    subcommand_help = "組織からユーザを脱退させます。"
    description = "組織からユーザを脱退させます。"
    epilog = "組織オーナまたは組織管理者ロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, command_help=subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
    return parser
