"""プロジェクトメンバの比較と同期計画。"""

import argparse
from dataclasses import dataclass
from typing import Literal

from annofabapi.models import ProjectMember

from annofabcli.common.cli import CommandLine

MEMBER_PROPERTIES = ("member_role", "sampling_inspection_rate", "sampling_acceptance_rate")
"""同期するメンバ情報。"""


@dataclass
class MemberDifference:
    """基準プロジェクトから同期先への差分。"""

    user_id: str
    """対象ユーザID。"""
    action: Literal["add", "update", "delete"]
    """一致させるために必要な操作。"""
    source: ProjectMember | None
    """基準プロジェクトの有効なメンバ情報。"""
    destination: ProjectMember | None
    """同期先のメンバ情報。脱退済みも含む。"""
    skip_reason: str = ""
    """同期できない理由。空文字なら同期可能。"""


class CompareProjectMembers(CommandLine):
    """メンバ構成の差分を取得する。"""

    def get_differences(self, src_project_id: str, dest_project_id: str) -> list[MemberDifference]:
        """メンバの有無・ロール・抜取率を比較する。

        Args:
            src_project_id: 基準プロジェクトID
            dest_project_id: 同期先プロジェクトID

        Returns:
            一致させるために必要な操作と、同期できない理由
        """
        self.require_project_access(src_project_id)
        self.require_project_access(dest_project_id)
        source = {m["user_id"]: m for m in self.service.wrapper.get_all_project_members(src_project_id) if m["member_status"] == "active"}
        destination = {m["user_id"]: m for m in self.service.wrapper.get_all_project_members(dest_project_id, query_params={"include_inactive_member": True})}
        src_org = self.facade.get_organization_name_from_project_id(src_project_id)
        dest_org = self.facade.get_organization_name_from_project_id(dest_project_id)
        src_accounts = {m["account_id"] for m in self.service.wrapper.get_all_organization_members(src_org)}
        dest_accounts = {m["account_id"] for m in self.service.wrapper.get_all_organization_members(dest_org)}
        differences = []
        for user_id in sorted(source.keys() | destination.keys()):
            src = source.get(user_id)
            dest = destination.get(user_id)
            active_dest = dest is not None and dest["member_status"] == "active"
            action: Literal["add", "update", "delete"]
            if src is None:
                if not active_dest:
                    continue
                action = "delete"
            elif not active_dest:
                action = "add"
            elif dest is not None and any(src.get(key) != dest.get(key) for key in MEMBER_PROPERTIES):
                action = "update"
            else:
                continue
            reason = ""
            if user_id == self.service.api.login_user_id:
                reason = "自分自身のメンバ情報は変更できません。"
            elif src is not None and src["account_id"] not in src_accounts:
                reason = "基準プロジェクトの組織に所属していません。"
            elif src is not None and src["account_id"] not in dest_accounts:
                reason = "同期先プロジェクトの組織に所属していません。"
            differences.append(MemberDifference(user_id, action, src, dest, reason))
        return differences


def add_comparison_arguments(parser: argparse.ArgumentParser) -> None:
    """比較するプロジェクトの引数を定義する。

    Args:
        parser: コマンドのパーサー

    Returns:
        None
    """
    parser.add_argument("--src_project_id", required=True, help="基準プロジェクトのproject_id")
    parser.add_argument("--dest_project_id", required=True, nargs="+", help="同期先のproject_id。複数指定可能です。 ``file://`` で一覧ファイルを指定できます。")
