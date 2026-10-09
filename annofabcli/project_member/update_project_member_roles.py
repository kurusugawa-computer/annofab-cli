import argparse

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.project_member.update_project_members import UpdatedProjectMember, UpdateProjectMembers


class UpdateProjectMemberRoles(UpdateProjectMembers):
    """複数ユーザに同じロールを設定する。"""

    def main(self) -> None:
        """対象ユーザのロールを一括更新する。

        Args:
            なし

        Returns:
            None
        """
        if self.args.all_users:
            user_ids = [member["user_id"] for member in self.service.wrapper.get_all_project_members(self.args.project_id) if member["user_id"] != self.service.api.login_user_id]
        else:
            user_ids = annofabcli.common.cli.get_list_from_args(self.args.user_id)
        role = ProjectMemberRole(self.args.role)
        members = [UpdatedProjectMember(user_id=user_id, member_role=role) for user_id in dict.fromkeys(user_ids)]
        self.update_project_members(self.args.project_id, members)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    UpdateProjectMemberRoles(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    ArgumentParser(parser).add_project_id()
    user_group = parser.add_mutually_exclusive_group(required=True)
    user_group.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help=(
            "ロールを更新するユーザIDを指定します。"
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
            " ファイルを読み込む場合は、ファイル指定を1個だけ渡してください。"
            "直接指定する値や別のファイル指定とは併用できません。"
        ),
    )
    user_group.add_argument("--all_users", action="store_true", help="自分以外のすべての有効なプロジェクトメンバを対象にします。")
    parser.add_argument("--role", required=True, choices=[role.value for role in ProjectMemberRole], help="対象ユーザに共通して設定するロールを指定します。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "update_role",
        "複数のプロジェクトメンバに同じロールを設定します。",
        description="複数ユーザのロールを一括更新します。抜取率は維持します。自分自身は更新できません。",
        epilog="オーナロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
