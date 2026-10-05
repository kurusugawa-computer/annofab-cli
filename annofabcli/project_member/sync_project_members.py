"""基準プロジェクトのメンバ構成を同期する。"""

import argparse
import logging

import requests
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import build_annofabapi_resource_and_login
from annofabcli.common.exceptions import ProjectAuthorizationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.project_member.compare_project_members import MEMBER_PROPERTIES, CompareProjectMembers, add_comparison_arguments

logger = logging.getLogger(__name__)


class SyncProjectMembers(CompareProjectMembers):
    """複数プロジェクトのメンバ構成を同期する。"""

    def sync_project_members(self, src_project_id: str, dest_project_id: str, *, delete_extra_members: bool = False) -> None:
        """差分のあるメンバだけを追加・更新・脱退させる。

        Args:
            src_project_id: 基準プロジェクトID
            dest_project_id: 同期先プロジェクトID
            delete_extra_members: 同期先にだけいるメンバを脱退させるか

        Returns:
            None
        """
        self.require_project_access(dest_project_id, [ProjectMemberRole.OWNER])
        differences = self.get_differences(src_project_id, dest_project_id)
        changes = []
        for difference in differences:
            if difference.skip_reason:
                logger.warning(f"user_id='{difference.user_id}' を同期できません。{difference.skip_reason}")
            elif difference.action != "delete" or delete_extra_members:
                changes.append(difference)
        if not changes:
            logger.info(f"同期する変更はありません。project_id='{dest_project_id}'")
            return
        counts = {action: sum(d.action == action for d in changes) for action in ("add", "update", "delete")}
        if not self.confirm_processing(f"'{src_project_id}' のメンバ構成を '{dest_project_id}' に同期しますか？追加: {counts['add']} 件、更新: {counts['update']} 件、脱退: {counts['delete']} 件"):
            return
        success_count = 0
        failure_count = 0
        for index, difference in enumerate(changes, start=1):
            logger.debug(f"{index} / {len(changes)} 件目: user_id='{difference.user_id}', action='{difference.action}'")
            if index % 100 == 0:
                logger.info(f"{index} / {len(changes)} 件目のメンバを同期中です。")
            member = difference.destination if difference.action == "delete" else difference.source
            assert member is not None
            request_body = {
                **{key: member.get(key) for key in MEMBER_PROPERTIES},
                "member_status": "inactive" if difference.action == "delete" else "active",
                "last_updated_datetime": difference.destination["updated_datetime"] if difference.destination is not None else None,
            }
            try:
                self.service.api.put_project_member(dest_project_id, difference.user_id, request_body=request_body)
                success_count += 1
            except requests.HTTPError:
                failure_count += 1
                logger.warning(f"メンバの同期に失敗しました。project_id='{dest_project_id}', user_id='{difference.user_id}'", exc_info=True)
        logger.info(f"メンバの同期が完了しました。project_id='{dest_project_id}', 成功: {success_count} 件、スキップ: {len(differences) - len(changes)} 件、失敗: {failure_count} 件")

    def main(self) -> None:
        """指定した同期先を順に処理する。

        Args:
            なし

        Returns:
            None
        """
        for project_id in dict.fromkeys(annofabcli.common.cli.get_list_from_args(self.args.dest_project_id)):
            try:
                self.sync_project_members(self.args.src_project_id, project_id, delete_extra_members=self.args.delete_extra_members)
            except (ProjectAuthorizationError, requests.HTTPError):
                logger.warning(f"プロジェクトへのメンバ同期に失敗しました。project_id='{project_id}'", exc_info=True)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    SyncProjectMembers(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "sync",
        "基準プロジェクトのメンバ構成を複数プロジェクトに同期します。",
        description="メンバの追加、ロール・抜取率の更新を行います。自分自身と組織外のメンバは変更しません。",
        epilog="同期先プロジェクトのオーナロールを持つユーザで実行してください。",
    )
    add_comparison_arguments(parser)
    parser.add_argument("--delete_extra_members", action="store_true", help="基準プロジェクトにいない同期先のメンバを脱退させます。自分自身は脱退させません。")
    parser.set_defaults(subcommand_func=main)
    return parser
