from __future__ import annotations

import logging

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
            ValueError(f"引数`df`には、{TaskHistory.columns}の列が必要です。")

        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0


    @classmethod
    def create_task_history_df(self) -> pandas.DataFrame:
        """
        タスク履歴の一覧のDataFrameを出力する。

        Returns:

        """
        task_histories_dict = self._get_task_histories_dict()
        task_list = self._get_task_list()

        all_task_history_list = []
        for task_id, task_history_list in task_histories_dict.items():
            task = self._get_task_from_task_id(task_list, task_id)
            if task is None:
                continue

            for history in task_history_list:
                account_id = history["account_id"]
                history["user_id"] = self._get_user_id(account_id)
                history["username"] = self._get_username(account_id)
                history["biography"] = self._get_biography(account_id)
                history["worktime_hour"] = annofabcli.common.utils.isoduration_to_hour(
                    history["accumulated_labor_time_milliseconds"]
                )
                # task statusがあると分析しやすいので追加する
                history["task_status"] = task["status"]
                all_task_history_list.append(history)

        df = pandas.DataFrame(
            all_task_history_list,
            columns=[
                "project_id",
                "task_id",
                "phase",
                "phase_stage",
                "account_id",
                "user_id",
                "username",
                "biography",
                "worktime_hour",
            ],
        )
        if len(df) == 0:
            logger.warning("タスク履歴の件数が0件です。")
        return df