"""
annofabapi.exceptions

This module contains the set of annofabapi exceptions.
"""

from typing import List, Optional  # pylint: disable=unused-import

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
    """
    AnnoFabの認可エラー
    """

    def __init__(self, project_title:str, roles: List[str]):
        msg = f"プロジェクト: {project_title} に、ロール: {roles} のいずれかが付与されていません。"
        super().__init__(msg)
