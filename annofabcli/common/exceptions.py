"""
annofabapi.exceptions

This module contains the set of annofabapi exceptions.
"""

from typing import List, Optional  # pylint: disable=unused-import

from annofabapi.models import OrganizationMemberRole, ProjectMemberRole


class AnnofabCliException(Exception):
    """
    annofabcliに関するException
    """


class AuthenticationError(AnnofabCliException):
    """
    AnnoFabの認証エラー
    """
    def __init__(self, loing_user_id: str):
        msg = f"AnnoFabにログインできませんでした。User ID: {loing_user_id}"
        super().__init__(msg)


class AuthorizationError(AnnofabCliException):
    pass


class ProjectAuthorizationError(AuthorizationError):
    """
    AnnoFabプロジェクトに関する認可エラー
    """
    def __init__(self, project_title: str, roles: List[ProjectMemberRole]):
        role_values = [e.value for e in roles]
        msg = f"プロジェクト: {project_title} に、ロール: {role_values} のいずれかが付与されていません。"
        super().__init__(msg)


class OrganizationAuthorizationError(AuthorizationError):
    """
    AnnoFab組織に関する認可エラー
    """
    def __init__(self, organization_name: str, roles: List[OrganizationMemberRole]):
        role_values = [e.value for e in roles]
        msg = f"組織: {organization_name} に、ロール: {role_values} のいずれかが付与されていません。"
        super().__init__(msg)
