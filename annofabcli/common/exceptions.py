"""
annofabapi.exceptions

This module contains the set of annofabapi exceptions.
"""

from typing import List

from annofabapi.models import OrganizationMemberRole, ProjectMemberRole


class AnnofabCliException(Exception):
    """
    annofabcliに関するException
    """


class AuthenticationError(AnnofabCliException):
    """
    Annofabの認証エラー
    """

    def __init__(self, loing_user_id: str) -> None:
        msg = f"Annofabにログインできませんでした。User ID: {loing_user_id}"
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

    def __init__(self, project_title: str, roles: List[ProjectMemberRole]) -> None:
        role_values = [e.value for e in roles]
        msg = f"プロジェクト: {project_title} に、ロール: {role_values} のいずれかが付与されていません。"
        super().__init__(msg)


class OrganizationAuthorizationError(AuthorizationError):
    """
    Annofab組織に関する認可エラー
    """

    def __init__(self, organization_name: str, roles: List[OrganizationMemberRole]) -> None:
        role_values = [e.value for e in roles]
        msg = f"組織: {organization_name} に、ロール: {role_values} のいずれかが付与されていません。"
        super().__init__(msg)


class MfaEnabledUserExecutionError(AnnofabCliException):
    """
    MFAが有効化されているユーザーが実行したことを示すエラー
    """

    def __init__(self, login_user_id: str) -> None:
        msg = f"ユーザー(User ID: {login_user_id})はMFAが有効化されているため、annofabcliを使用できません。"
        super().__init__(msg)
