"""プロジェクトのメンバ構成の差分を出力する。"""

import argparse
import logging

import yaml
from pydantic import BaseModel, Field

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string, print_json
from annofabcli.project_member.compare_project_members import MEMBER_PROPERTIES

logger = logging.getLogger(__name__)

MemberValue = str | int | float | None
"""ロールまたは抜取率の値。"""

MemberTextValue = str | list[str] | dict[str, dict[str, MemberValue]]
"""テキスト表示するメンバのID、変更項目名、または変更値。"""


class MemberValueDiff(BaseModel):
    """メンバのプロパティの左右の値。"""

    left: MemberValue
    """左側の値。"""
    right: MemberValue
    """右側の値。"""


class ChangedMember(BaseModel):
    """両プロジェクトに所属するメンバの変更項目。"""

    user_id: str
    """ユーザID。"""
    changes: dict[str, MemberValueDiff]
    """値が異なるプロパティ。"""


class ProjectMembersDiff(BaseModel):
    """左から右へのメンバ構成の差分。"""

    left_project_id: str
    """左側のプロジェクトID。"""
    right_project_id: str
    """右側のプロジェクトID。"""
    added_user_ids: list[str] = Field(default_factory=list)
    """右側にだけ所属するユーザID。"""
    removed_user_ids: list[str] = Field(default_factory=list)
    """左側にだけ所属するユーザID。"""
    changed_members: list[ChangedMember] = Field(default_factory=list)
    """両側に所属し、プロパティが異なるメンバ。"""


def format_diff_as_text(diff: ProjectMembersDiff, *, detail: bool) -> str:
    """変更のある項目を階層形式で表示する。

    Args:
        diff: 左から右への差分。
        detail: 変更前後の値を表示するか。

    Returns:
        差分テキスト。差分がなければ空文字。
    """
    section: dict[str, list[str] | list[dict[str, MemberTextValue]]] = {}
    if diff.added_user_ids:
        section["added"] = diff.added_user_ids
    if diff.removed_user_ids:
        section["removed"] = diff.removed_user_ids
    if diff.changed_members:
        changed_items: list[dict[str, MemberTextValue]] = []
        for member in diff.changed_members:
            if detail:
                changed_items.append(member.model_dump())
            else:
                changed_items.append({"user_id": member.user_id, "fields": list(member.changes)})
        section["changed"] = changed_items
    if not section:
        return ""
    return "[project_members]\n" + yaml.safe_dump({"left_project_id": diff.left_project_id, "right_project_id": diff.right_project_id, **section}, allow_unicode=True, sort_keys=False).rstrip()


class DiffProjectMembers(CommandLine):
    """同期操作とは独立したメンバ構成の差分を表示する。"""

    def get_diff(self, left_project_id: str, right_project_id: str) -> ProjectMembersDiff:
        """有効なメンバの所属・ロール・抜取率を比較する。

        Args:
            left_project_id: 左側のプロジェクトID。
            right_project_id: 右側のプロジェクトID。

        Returns:
            左から右への差分。
        """
        self.require_project_access(left_project_id)
        self.require_project_access(right_project_id)
        left_members = {m["user_id"]: m for m in self.service.wrapper.get_all_project_members(left_project_id) if m["member_status"] == "active"}
        right_members = {m["user_id"]: m for m in self.service.wrapper.get_all_project_members(right_project_id) if m["member_status"] == "active"}
        diff = ProjectMembersDiff(
            left_project_id=left_project_id,
            right_project_id=right_project_id,
            added_user_ids=sorted(right_members.keys() - left_members.keys()),
            removed_user_ids=sorted(left_members.keys() - right_members.keys()),
        )
        for user_id in sorted(left_members.keys() & right_members.keys()):
            left = left_members[user_id]
            right = right_members[user_id]
            changes = {key: MemberValueDiff(left=left.get(key), right=right.get(key)) for key in MEMBER_PROPERTIES if left.get(key) != right.get(key)}
            if changes:
                diff.changed_members.append(ChangedMember(user_id=user_id, changes=changes))
        return diff

    def main(self) -> None:
        """差分をテキストまたはJSONに出力する。リソースは変更しない。

        Args:
            なし

        Returns:
            None
        """
        diff = self.get_diff(self.args.left_project_id, self.args.right_project_id)
        count = len(diff.added_user_ids) + len(diff.removed_user_ids) + len(diff.changed_members)
        logger.info(f"メンバ構成の差分: {count} 件")
        if self.args.format in ("text", "detail_text"):
            text = format_diff_as_text(diff, detail=self.args.format == "detail_text")
            if not text:
                logger.info("差分はありません。")
            if text or self.args.output is not None:
                output_string(text, self.args.output)
        else:
            print_json(diff.model_dump(), is_pretty=self.args.format == "pretty_json", output=self.args.output)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    DiffProjectMembers(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(subparsers, "diff", "左から右へのプロジェクトのメンバ構成の差分を出力します。")
    parser.add_argument("--left_project_id", required=True, help="比較元のプロジェクトのproject_id")
    parser.add_argument("--right_project_id", required=True, help="比較先のプロジェクトのproject_id")
    parser.add_argument(
        "-f",
        "--format",
        choices=["text", "detail_text", "json", "pretty_json"],
        default="text",
        help=(
            "出力フォーマット\n\n"
            "* text: 差分項目のみをセクション見出し付きの階層形式で表示する\n"
            "* detail_text: 差分項目と比較元・比較先の値をchanges配下のleft/right形式で表示する\n"
            "* json: 差分情報をJSONで出力する\n"
            "* pretty_json: 差分情報を整形JSONで出力する\n"
        ),
    )
    ArgumentParser(parser).add_output()
    parser.set_defaults(subcommand_func=main)
    return parser
