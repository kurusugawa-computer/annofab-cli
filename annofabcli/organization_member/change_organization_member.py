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


class ChangeOrganizationMemberMain(CommandLineWithConfirm):
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

    def main(self, organization_name: str, user_ids: Collection[str], role: str) -> None:
        logger.info(f"{len(user_ids)} 件の組織メンバのロールを'{role}'に変更します。")

        member_list = self.service.wrapper.get_all_organization_members(organization_name)

        # プロジェクトメンバを追加/更新する
        success_count = 0
        for user_id in user_ids:
            member = self.get_member(member_list, user_id)
            if member is None:
                logger.warning(f"組織メンバにuser_id='{user_id}'のユーザが存在しません。")
                continue

            if not self.confirm_processing(f"user_id='{user_id}'のユーザの組織メンバロールを'{role}'に変更しますか？ :: username='{member['username']}', role='{member['role']}'"):
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
                logger.warning(f"user_id='{user_id}'のユーザの組織メンバロールを'{role}'に変更させるのに失敗しました。", exc_info=True)

        logger.info(f"{success_count} / {len(user_ids)} 件のユーザの組織メンバロールを'{role}'に変更しました。")


class ChangeOrganizationMember(CommandLine):
    def main(self) -> None:
        args = self.args

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        main_obj = ChangeOrganizationMemberMain(self.service, all_yes=args.yes)
        main_obj.main(organization_name=args.organization, user_ids=user_id_list, role=args.role)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ChangeOrganizationMember(service, facade, args).main()


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
        help="指定した場合、組織メンバのロールを変更します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    # 2022/01時点でロールしか変更できないのに、change_roleという名前でなくchangeという名前にしたのは、将来的にロール以外も変更できるようにするため
    subcommand_name = "change"
    subcommand_help = "組織メンバの情報（ロールなど）を変更します。"
    description = "組織メンバの情報（ロールなど）を変更します。"
    epilog = "組織オーナまたは組織管理者ロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, command_help=subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
