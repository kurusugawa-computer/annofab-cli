"""
annofabapi.exceptions

This module contains the set of annofabapi exceptions.
"""


class AnnofabCliException(Exception):
    """
    annofabcliに関するException
    """


class UnauthorizationError(AnnofabCliException):
    """
    AnnoFabの認証エラー
    """

    def __init__(self, loing_user_id: str):
        msg = f"AnnoFabにログインできませんでした。User ID: {loing_user_id}"
        super().__init__(msg)
