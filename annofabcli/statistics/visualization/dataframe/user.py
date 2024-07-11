from __future__ import annotations

import logging

import pandas

logger = logging.getLogger(__name__)


class User:
    """
    ユーザー情報が格納されたDataFrameをラップしたクラスです。
    DataFrameには以下の列が存在します。
    * user_id
    * account_id
    * username
    * biography
    """

    columns = ["user_id", "account_id", "username", "biography"]  # noqa: RUF012

    @staticmethod
    def _duplicated_keys(df: pandas.DataFrame) -> bool:
        """
        DataFrameに重複したキーがあるかどうかを返します。
        """
        duplicated1 = df.duplicated(subset=["user_id"])
        duplicated2 = df.duplicated(subset=["account_id"])
        return duplicated1.any() or duplicated2.any()

    @classmethod
    def required_columns_exist(cls, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(User.columns) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns}の列が必要です。 :: {df.columns=}")

        if self._duplicated_keys(df):
            logger.warning(f"引数`df`の`user_id`列または`account_id`が重複しています。 :: {df.columns=}")

        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0
