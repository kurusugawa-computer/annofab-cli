from __future__ import annotations

import logging
from pathlib import Path

import pandas

logger = logging.getLogger(__name__)


class ActualWorktime:
    """
    実績作業時間情報が格納されたDataFrameをラップしたクラスです。
    DataFrameには以下の列が存在します。
    * project_id
    * date
    * account_id
    * actual_worktime_hour
    `project_id`,`date`, `account_id`のペアがユニークなキーです。
    """

    columns = ["project_id", "date", "account_id", "actual_worktime_hour"]

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def from_csv(cls, csv_file: Path) -> ActualWorktime:
        df = pandas.read_csv(str(csv_file))
        return cls(df)

    @classmethod
    def empty(cls) -> ActualWorktime:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "account_id": "string",
            "actual_worktime_hour": "float64",
        }

        df = pandas.DataFrame(columns=cls.columns).astype(df_dtype)
        return cls(df)
