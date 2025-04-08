"""
annofabapi.exceptions

This module contains the set of annofabapi exceptions.
"""

from annofabapi.models import OrganizationMemberRole, ProjectMemberRole


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

    def __init__(self, project_title: str, roles: list[ProjectMemberRole]) -> None:
        role_values = [e.value for e in roles]
        msg = f"プロジェクト'{project_title}'に対して、ロール'{role_values}'のいずれかが必要です。"
        super().__init__(msg)


class OrganizationAuthorizationError(AuthorizationError):
    """
    Annofab組織に関する認可エラー
    """

    def __init__(self, organization_name: str, roles: list[OrganizationMemberRole]) -> None:
        role_values = [e.value for e in roles]
        msg = f"組織'{organization_name}'に対して、ロール'{role_values}'のいずれかが必要です。"
        super().__init__(msg)


class MfaEnabledUserExecutionError(AnnofabCliException):
    """
    MFAが有効化されているユーザーが実行したことを示すエラー
    """

    def __init__(self, login_user_id: str) -> None:
        msg = f"MFAによるログインで失敗しました。User ID: {login_user_id}"
        super().__init__(msg)
