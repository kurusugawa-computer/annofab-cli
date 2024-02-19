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

    columns = ["user_id", "account_id", "username", "biography"]

    @staticmethod
    def required_columns_exist(df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(User.columns) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if not self.required_columns_exist(df):
            ValueError(f"引数`df`には、{User.columns}の列が必要です。")
        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0
