from __future__ import annotations

import logging
from typing import Any

import pandas

logger = logging.getLogger(__name__)


class TaskHistory:
    """
    タスク履歴情報が格納されたDataFrameをラップしたクラスです。
    DataFrameには以下の列が存在します。
    * project_id
    * task_id
    * phase
    * phase_stage
    * account_id
    * worktime_hour
    """

    columns = ["project_id", "task_id", "phase", "phase_stage", "account_id", "worktime_hour"]

    @staticmethod
    def required_columns_exist(df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(TaskHistory.columns) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{TaskHistory.columns}の列が必要です。")

        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def from_api_response(cls, task_histories: dict[str, list[dict[str, Any]]]) -> TaskHistory:
        """
        APIから取得したタスク履歴情報を元に、TaskHistoryを作成します。

        Args:
            task_histories: key:task_id, value:タスク履歴リスト

        """

        all_task_history_list = []
        for task_history_list in task_histories.values():
            all_task_history_list.extend(task_history_list)

        df = pandas.DataFrame(all_task_history_list)
        return cls(df)
