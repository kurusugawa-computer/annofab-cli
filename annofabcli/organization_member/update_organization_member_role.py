from __future__ import annotations

import argparse
import logging
from collections.abc import Collection
from typing import Any

import annofabapi
import more_itertools
from annofabapi.models import OrganizationMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import (
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class UpdateOrganizationMemberRoleMain(CommandLineWithConfirm):
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
    def get_member(organization_member_list: list[dict[str, Any]], user_id: str) -> dict[str, Any] | None:
        return more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)

    def main(self, organization_name: str, user_ids: Collection[str], role: str) -> None:
        logger.info(f"{len(user_ids)} 件の組織メンバのロールを'{role}'に変更します。")

        member_list = self.service.wrapper.get_all_organization_members(organization_name)

        success_count = 0
        skipped_count = 0
        failed_count = 0
        for index, user_id in enumerate(user_ids, start=1):
            logger.debug(f"組織'{organization_name}': {index} / {len(user_ids)} 件目を処理します。user_id='{user_id}'")
            if index % 100 == 0:
                logger.info(f"組織'{organization_name}': {index} / {len(user_ids)} 件目を処理します。")
            member = self.get_member(member_list, user_id)
            if member is None:
                logger.warning(f"組織メンバにuser_id='{user_id}'のユーザが存在しません。")
                skipped_count += 1
                continue

            if not self.confirm_processing(f"user_id='{user_id}'のユーザの組織メンバロールを'{role}'に変更しますか？ :: username='{member['username']}', role='{member['role']}'"):
                skipped_count += 1
                continue

            try:
                self.service.api.update_organization_member_role(
                    organization_name,
                    user_id,
                    request_body={"role": role, "last_updated_datetime": member["updated_datetime"]},
                )
                logger.debug(f"user_id='{user_id}'のユーザの組織メンバロールを'{role}'に変更しました。")
                success_count += 1

            except Exception:  # pylint: disable=broad-except
                failed_count += 1
                logger.warning(f"user_id='{user_id}'のユーザの組織メンバロールを'{role}'に変更させるのに失敗しました。", exc_info=True)

        logger.info(f"組織'{organization_name}'の処理が完了しました。成功: {success_count} 件、スキップ: {skipped_count} 件、失敗: {failed_count} 件、合計: {len(user_ids)} 件")


class UpdateOrganizationMemberRole(CommandLine):
    def main(self) -> None:
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = UpdateOrganizationMemberRoleMain(self.service, all_yes=args.yes)
        main_obj.main(organization_name=args.organization, user_ids=user_id_list, role=args.role)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateOrganizationMemberRole(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-org", "--organization", required=True, type=str, help="対象の組織の組織名を指定してください。")

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        required=True,
        help="変更対象ユーザのuser_idを指定してください。 ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。",
    )

    role_choices = [e.value for e in OrganizationMemberRole]
    parser.add_argument(
        "--role",
        type=str,
        choices=role_choices,
        required=True,
        help="対象ユーザに設定するロールを指定します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_role"
    subcommand_help = "組織メンバのロールを更新します。"
    description = "組織メンバのロールを更新します。"
    epilog = "組織オーナまたは組織管理者ロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, command_help=subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
