import argparse
import logging
import sys
from pathlib import Path

import pandas
import requests
from annofabapi.models import ProjectMemberRole, ProjectMemberStatus
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class UpdatedProjectMember(BaseModel):
    """既存のプロジェクトメンバに適用する部分更新。"""

    model_config = ConfigDict(extra="forbid")
    """未対応のキーは入力エラーにする。"""

    user_id: str = Field(min_length=1)
    """更新対象のユーザID。"""
    member_role: ProjectMemberRole | None = None
    """指定した場合のみ更新するロール。nullは指定できない。"""
    sampling_inspection_rate: int | None = Field(default=None, strict=True, ge=0, le=100)
    """抜取検査率。省略時は維持し、nullなら解除する。"""
    sampling_acceptance_rate: int | None = Field(default=None, strict=True, ge=0, le=100)
    """抜取受入率。省略時は維持し、nullなら解除する。"""

    @field_validator("member_role")
    @classmethod
    def validate_member_role(cls, value: ProjectMemberRole | None) -> ProjectMemberRole:
        """明示的なロールのnull指定を拒否する。

        Args:
            value: 入力されたロール

        Returns:
            検証済みのロール
        """
        if value is None:
            raise ValueError("member_roleにnullは指定できません。変更しない場合はキーを省略してください。")
        return value


def parse_project_member_updates(value: object) -> list[UpdatedProjectMember]:
    """更新情報の配列を検証する。

    Args:
        value: JSONまたはCSVから読み込んだ更新情報

    Returns:
        検証済みの更新情報
    """
    members = TypeAdapter(list[UpdatedProjectMember]).validate_python(value)
    user_ids = [member.user_id for member in members]
    if len(user_ids) != len(set(user_ids)):
        raise ValueError("user_idは重複させないでください。")
    return members


def read_project_member_updates_from_csv(csv_path: Path) -> list[UpdatedProjectMember]:
    """CSVから更新情報を読み込む。空欄のプロパティは更新しない。

    Args:
        csv_path: 入力CSVのパス

    Returns:
        検証済みの更新情報
    """
    df = pandas.read_csv(csv_path, dtype={"user_id": "string", "member_role": "string", "sampling_inspection_rate": "Int64", "sampling_acceptance_rate": "Int64"})
    if "user_id" not in df.columns:
        raise ValueError("CSVにはuser_id列が必要です。")
    records = [{key: value for key, value in row.items() if key == "user_id" or value is not None} for row in df.to_dict("records")]
    return parse_project_member_updates(records)


class UpdateProjectMembers(CommandLine):
    """既存のプロジェクトメンバを部分更新する。"""

    def update_project_members(self, project_id: str, members: list[UpdatedProjectMember]) -> None:
        """指定されたプロパティだけを更新する。自分自身のロール変更と非所属ユーザはスキップする。

        Args:
            project_id: 対象のプロジェクトID
            members: ユーザごとの更新情報

        Returns:
            None
        """
        self.require_project_access(project_id, [ProjectMemberRole.OWNER])
        old_members = {member["user_id"]: member for member in self.service.wrapper.get_all_project_members(project_id)}
        success_count = 0
        skipped_count = 0
        failure_count = 0
        logger.info(f"{len(members)} 件のプロジェクトメンバを更新します。project_id='{project_id}'")
        for index, member in enumerate(members, start=1):
            logger.debug(f"{index} / {len(members)} 件目: user_id='{member.user_id}'")
            if index % 100 == 0:
                logger.info(f"{index} / {len(members)} 件目のプロジェクトメンバを処理中です。")
            old_member = old_members.get(member.user_id)
            changes = member.model_dump(mode="json", exclude_unset=True, exclude={"user_id"})
            if old_member is None or old_member["member_status"] != ProjectMemberStatus.ACTIVE.value:
                logger.warning(f"user_id='{member.user_id}' は有効なプロジェクトメンバでないため更新できません。")
            elif member.user_id == self.service.api.login_user_id and changes.get("member_role", old_member["member_role"]) != old_member["member_role"]:
                logger.warning(f"user_id='{member.user_id}' は自分自身のロールを変更できないため更新をスキップします。")
            elif not changes:
                logger.warning(f"user_id='{member.user_id}' の更新内容が指定されていません。")
            elif self.confirm_processing(f"user_id='{member.user_id}' のメンバ情報を更新しますか？ project_id='{project_id}', 更新内容={changes}"):
                request_body = {
                    "member_status": old_member["member_status"],
                    "member_role": old_member["member_role"],
                    "sampling_inspection_rate": old_member["sampling_inspection_rate"],
                    "sampling_acceptance_rate": old_member["sampling_acceptance_rate"],
                    "last_updated_datetime": old_member["updated_datetime"],
                    **changes,
                }
                try:
                    self.service.api.put_project_member(project_id, member.user_id, request_body=request_body)
                    success_count += 1
                    logger.debug(f"user_id='{member.user_id}' のプロジェクトメンバ情報を更新しました。")
                except requests.HTTPError:
                    failure_count += 1
                    logger.warning(f"user_id='{member.user_id}' のプロジェクトメンバ情報の更新に失敗しました。", exc_info=True)
                continue
            skipped_count += 1
        logger.info(f"メンバ情報の更新が完了しました。成功: {success_count} 件、スキップ: {skipped_count} 件、失敗: {failure_count} 件。project_id='{project_id}'")

    def main(self) -> None:
        """CSVまたはJSONの更新情報を適用する。

        Args:
            なし

        Returns:
            None
        """
        try:
            if self.args.csv is not None:
                members = read_project_member_updates_from_csv(self.args.csv)
            else:
                members = parse_project_member_updates(annofabcli.common.cli.get_json_from_args(self.args.json))
        except ValueError as exc:
            print(f"annofabcli project_member update: error: {exc}", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        self.update_project_members(self.args.project_id, members)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    UpdateProjectMembers(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    ArgumentParser(parser).add_project_id()
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--csv",
        type=Path,
        help="更新対象と更新後の値が記載されたCSVファイルのパスを指定します。ヘッダ行あり、カンマ区切りです。\n"
        "必須列: user_id\n任意列: member_role, sampling_inspection_rate, sampling_acceptance_rate\n"
        "空欄の値は変更しません。抜取率の設定解除には ``--json`` を使用してください。",
    )
    input_group.add_argument(
        "--json",
        type=str,
        help="更新対象と更新後の値をJSONオブジェクトの配列で指定します。キーはCSVの列に対応します。\n"
        "``file://`` を先頭に付けるとJSONファイルを指定できます。\n"
        "キーを省略すると値を維持します。抜取率にnullを指定すると設定を解除します。member_roleにnullは指定できません。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "update",
        "CSVまたはJSONでプロジェクトメンバ情報を更新します。",
        description="既存のプロジェクトメンバのロール、抜取検査率、抜取受入率を更新します。自分自身の抜取率も更新できますが、ロールは変更できません。",
        epilog="オーナロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
