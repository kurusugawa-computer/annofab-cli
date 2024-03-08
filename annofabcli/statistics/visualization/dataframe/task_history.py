from __future__ import annotations

import copy
import logging
from typing import Any

import pandas

from annofabcli.common.utils import isoduration_to_hour

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

    columns = ["project_id", "task_id", "phase", "phase_stage", "account_id", "worktime_hour"]  # noqa: RUF012

    @classmethod
    def required_columns_exist(cls, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(cls.columns) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns}の列が必要です。 :: {df.columns=}")

        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def from_api_content(cls, task_histories: dict[str, list[dict[str, Any]]]) -> TaskHistory:
        """
        APIから取得したタスク履歴情報を元に、TaskHistoryを作成します。

        Args:
            task_histories: key:task_id, value:タスク履歴リスト

        """

        all_task_history_list = []
        for task_history_list in task_histories.values():
            for task_history in task_history_list:
                new_task_history = copy.deepcopy(task_history)
                new_task_history["worktime_hour"] = isoduration_to_hour(task_history["accumulated_labor_time_milliseconds"])
                all_task_history_list.append(new_task_history)

        if len(all_task_history_list) > 0:
            df = pandas.DataFrame(all_task_history_list)
        else:
            df = cls.empty()

        return cls(df)

    @classmethod
    def empty(cls) -> TaskHistory:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "phase": "string",
            "phase_stage": "int",
            "account_id": "string",
            "worktime_hour": "float64",
        }

        df = pandas.DataFrame(columns=cls.columns).astype(df_dtype)
        return cls(df)
