from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas

from annofabcli.common.utils import print_csv

logger = logging.getLogger(__name__)


class TaskWorktimeByPhaseUser:
    """
    タスクの作業時間をユーザーごとフェーズごとに並べたDataFrameをラップしたクラス。
    project_id, task_id, phase, phase_stage, account_idごとに、以下の情報が格納されています。
        * 計測作業時間
        * 生産量（タスク数、入力データ数、アノテーション数）
        * 品質情報（指摘コメント数、差し戻し回数）
    """

    @staticmethod
    def _duplicated_keys(df: pandas.DataFrame) -> bool:
        """
        DataFrameに重複したキーがあるかどうかを返します。
        """
        duplicated = df.duplicated(subset=["project_id", "task_id", "phase", "phase_stage", "account_id"])
        return duplicated.any()

    def __init__(self, df: pandas.DataFrame) -> None:
        if self._duplicated_keys(df):
            logger.warning("引数`df`に重複したキー（project_id, task_id, phase, phase_stage, account_id）が含まれています。")

        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_df(
        cls, df_worktime_ratio: pandas.DataFrame, df_user: pandas.DataFrame, df_task: pandas.DataFrame, project_id: str
    ) -> TaskWorktimeByPhaseUser:
        """
        AnnoWorkの実績時間から、作業者ごとに生産性を算出する。

        Args:
            df_worktime_ratio: 作業したタスク数を、作業時間で按分した値が格納されたDataFrame. 以下の列を参照する。
            df_user: ユーザー情報が格納されたDataFrame
            df_task: タスク情報が格納されたDataFrame。以下の列を参照します。
                * task_id
                * status
            project_id
        """
        df = df_worktime_ratio.merge(df_user, on="account_id", how="left")
        df = df.merge(df_task[["task_id", "status"]], on="task_id", how="left")
        df["project_id"] = project_id
        return cls(df)

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        columns = [
            "project_id",
            "task_id",
            "status",
            "phase",
            "phase_stage",
            "account_id",
            "user_id",
            "username",
            "biography",
            "worktime_hour",
            "task_count",
            "input_data_count",
            "annotation_count",
            "pointed_out_inspection_comment_count",
            "rejected_count",
        ]

        print_csv(self.df[columns], str(output_file))

    @staticmethod
    def merge(*obj: TaskWorktimeByPhaseUser) -> TaskWorktimeByPhaseUser:
        """
        複数のインスタンスをマージします。


        """
        df_list = [e.df for e in obj]
        df_merged = pandas.concat(df_list)
        return TaskWorktimeByPhaseUser(df_merged)

    @classmethod
    def empty(cls) -> TaskWorktimeByPhaseUser:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "phase": "string",
            "phase_stage": "int64",
            "status": "string",
            "account_id": "string",
            "user_id": "string",
            "username": "string",
            "biography": "string",
            "worktime_hour": "float64",
            "task_count": "float64",
            "input_data_count": "float64",
            "annotation_count": "float64",
            "pointed_out_inspection_comment_count": "float64",
            "rejected_count": "float64",
        }

        df = pandas.DataFrame(columns=df_dtype.keys()).astype(df_dtype)
        return cls(df)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def from_csv(cls, csv_file: Path) -> TaskWorktimeByPhaseUser:
        df = pandas.read_csv(str(csv_file))
        return cls(df)

    def mask_user_info(
        self,
        to_replace_for_user_id: Optional[dict[str, str]] = None,
        to_replace_for_username: Optional[dict[str, str]] = None,
        to_replace_for_account_id: Optional[dict[str, str]] = None,
        to_replace_for_biography: Optional[dict[str, str]] = None,
    ) -> TaskWorktimeByPhaseUser:
        """
        引数から渡された情報を元に、インスタンス変数`df`内のユーザー情報をマスクして、新しいインスタンスを返します。

        Args:
            to_replace_for_user_id: user_idを置換するためのdict。keyは置換前のuser_id, valueは置換後のuser_id。
            to_replace_for_username: usernameを置換するためのdict。keyは置換前のusername, valueは置換後のusername。
            to_replace_for_account_id: account_idを置換するためのdict。keyは置換前のaccount_id, valueは置換後のaccount_id。
            to_replace_for_biography: biographyを置換するためのdict。keyは置換前のbiography, valueは置換後のbiography。

        """
        to_replace_info = {
            "user_id": to_replace_for_user_id,
            "username": to_replace_for_username,
            "account_id": to_replace_for_account_id,
            "biography": to_replace_for_biography,
        }
        df = self.df.replace(to_replace_info)
        return TaskWorktimeByPhaseUser(df)
