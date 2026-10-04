"""annofabcliで使用する例外。"""

from annofabapi.models import OrganizationMemberRole, ProjectMemberRole

PROJECT_MEMBER_ROLE_LABELS = {
    ProjectMemberRole.OWNER: "オーナー",
    ProjectMemberRole.ACCEPTER: "チェッカー",
    ProjectMemberRole.WORKER: "アノテータ",
    ProjectMemberRole.TRAINING_DATA_USER: "アノテーションユーザ",
}
"""プロジェクトメンバロールの表示名。"""


def _format_required_roles(role_names: list[str]) -> str:
    """必要なロールをエラーメッセージ用に整形する。

    Args:
        role_names: ロール名の一覧。

    Returns:
        必要なロールを表す文字列。
    """
    names = "、".join(role_names)
    return names if len(role_names) == 1 else f"{names}のいずれか"


class AnnofabCliException(Exception):  # noqa: N818
    """
    annofabcliに関するException
    """


class AuthenticationError(AnnofabCliException):
    """
    Annofabの認証エラー
    """

    def __init__(self, login_user_id: str) -> None:
        msg = f"Annofabにログインできませんでした。User ID: {login_user_id}"
        super().__init__(msg)


class UpdatedFileForDownloadingError(AnnofabCliException):
    """
    ダウンロード対象ファイルの更新処理のエラー
    """


class DownloadingFileNotFoundError(AnnofabCliException):
    """
    ダウンロード対象のファイルが存在しないときのエラー
    """


class AuthorizationError(AnnofabCliException):
    pass


class ProjectAuthorizationError(AuthorizationError):
    """
    Annofabプロジェクトに関する認可エラー
    """

    def __init__(self, project_title: str, roles: list[ProjectMemberRole], *, operation: str | None = None) -> None:
        target = f"プロジェクト'{project_title}'"
        action = f"で{operation}には" if operation is not None else "に対しては"
        role_names = [f"{PROJECT_MEMBER_ROLE_LABELS[role]}ロール（{role.value}）" for role in roles]
        msg = f"{target}{action}、{_format_required_roles(role_names)}が必要です。"
        super().__init__(msg)


class OrganizationAuthorizationError(AuthorizationError):
    """
    Annofab組織に関する認可エラー
    """

    def __init__(self, organization_name: str, roles: list[OrganizationMemberRole], *, operation: str | None = None) -> None:
        target = f"組織'{organization_name}'"
        action = f"で{operation}には" if operation is not None else "に対しては"
        role_names = [f"'{role.value}'ロール" for role in roles]
        msg = f"{target}{action}、{_format_required_roles(role_names)}が必要です。"
        super().__init__(msg)


class MfaEnabledUserExecutionError(AnnofabCliException):
    """
    MFAが有効化されているユーザーが実行したことを示すエラー
    """

    def __init__(self, login_user_id: str) -> None:
        msg = f"MFAによるログインで失敗しました。User ID: {login_user_id}"
        super().__init__(msg)
