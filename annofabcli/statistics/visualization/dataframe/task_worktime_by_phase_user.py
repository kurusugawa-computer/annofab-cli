from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas
from annofabapi.models import TaskPhase

from annofabcli.common.utils import print_csv
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_history import TaskHistory
from annofabcli.statistics.visualization.dataframe.user import User

logger = logging.getLogger(__name__)


class TaskWorktimeByPhaseUser:
    """
    タスクの作業時間をユーザーごとフェーズごとに並べたDataFrameをラップしたクラス。
    project_id, task_id, phase, phase_stage, account_idごとに、以下の情報が格納されています。
        * 計測作業時間
        * 生産量（タスク数、入力データ数、アノテーション数）
        * 品質情報（指摘コメント数、差し戻し回数）
    """

    columns = [  # noqa: RUF012
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

    @classmethod
    def required_columns_exist(cls, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(cls.columns) - set(df.columns)) == 0

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

        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns}の列が必要です。 :: {df.columns=}")

        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_df_wrapper(cls, task_history: TaskHistory, user: User, task: Task, project_id: str) -> TaskWorktimeByPhaseUser:
        """
        以下のDataFrameのラッパーからインスタンスを生成します。
        * タスク履歴
        * ユーザー情報
        * タスク情報

        Args:
            task_history: タスク履歴が格納されたDataFrameをラップするクラス
            user: ユーザー情報が格納されたDataFrameをラップするクラスのインスタンス
            task: タスク情報が格納されたDataFrameをラップするクラスのインスタンス
            project_id
        """
        df_task = task.df
        df_worktime_ratio = cls._create_annotation_count_ratio_df(task_history.df, task.df)
        if len(df_worktime_ratio) == 0:
            return cls.empty()

        df = df_worktime_ratio.merge(user.df, on="account_id", how="left")
        df = df.merge(df_task[["task_id", "status"]], on="task_id", how="left")
        df["project_id"] = project_id
        return cls(df)

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        print_csv(self.df[self.columns], str(output_file))

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

    @staticmethod
    def _create_annotation_count_ratio_df(task_history_df: pandas.DataFrame, task_df: pandas.DataFrame) -> pandas.DataFrame:
        """
        task_id, phase, (phase_index), user_idの作業時間比から、アノテーション数などの生産量を求める

        Args:

        Returns:


        """
        annotation_count_dict = {
            row["task_id"]: {
                "annotation_count": row["annotation_count"],
                "input_data_count": row["input_data_count"],
                "inspection_comment_count": row["inspection_comment_count"],
                "rejected_count": row["number_of_rejections_by_inspection"] + row["number_of_rejections_by_acceptance"],
            }
            for _, row in task_df.iterrows()
        }

        def get_inspection_comment_count(row: pandas.Series) -> float:
            task_id = row.name[0]
            inspection_comment_count = annotation_count_dict[task_id]["inspection_comment_count"]
            return row["task_count"] * inspection_comment_count

        def get_rejected_count(row: pandas.Series) -> float:
            task_id = row.name[0]
            rejected_count = annotation_count_dict[task_id]["rejected_count"]
            return row["task_count"] * rejected_count

        def get_annotation_count(row: pandas.Series) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["annotation_count"]
            result = row["task_count"] * annotation_count
            return result

        def get_input_data_count(row: pandas.Series) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["input_data_count"]
            return row["task_count"] * annotation_count

        if len(task_df) == 0:
            logger.warning("タスク一覧が0件です。")
            return pandas.DataFrame()

        task_history_df = task_history_df[task_history_df["task_id"].isin(set(task_df["task_id"]))]

        group_obj = task_history_df.groupby(["task_id", "phase", "phase_stage", "account_id"]).agg({"worktime_hour": "sum"})
        # 担当者だけ変更して作業していないケースを除外する
        group_obj = group_obj[group_obj["worktime_hour"] > 0]

        if len(group_obj) == 0:
            logger.warning("タスク履歴情報に作業しているタスクがありませんでした。タスク履歴全件ファイルが更新されていない可能性があります。")
            return pandas.DataFrame(
                columns=[
                    "task_id",
                    "phase",
                    "phase_stage",
                    "account_id",
                    "worktime_hour",
                    "task_count",
                    "annotation_count",
                    "input_data_count",
                    "pointed_out_inspection_comment_count",
                    "rejected_count",
                ]
            )

        group_obj["task_count"] = group_obj.groupby(level=["task_id", "phase", "phase_stage"], group_keys=False).apply(
            lambda e: e / e["worktime_hour"].sum()
        )
        group_obj["annotation_count"] = group_obj.apply(get_annotation_count, axis="columns")
        group_obj["input_data_count"] = group_obj.apply(get_input_data_count, axis="columns")
        group_obj["pointed_out_inspection_comment_count"] = group_obj.apply(get_inspection_comment_count, axis="columns")
        group_obj["rejected_count"] = group_obj.apply(get_rejected_count, axis="columns")
        new_df = group_obj.reset_index()
        new_df["pointed_out_inspection_comment_count"] = new_df["pointed_out_inspection_comment_count"] * new_df["phase"].apply(
            lambda e: 1 if e == TaskPhase.ANNOTATION.value else 0
        )
        new_df["rejected_count"] = new_df["rejected_count"] * new_df["phase"].apply(lambda e: 1 if e == TaskPhase.ANNOTATION.value else 0)
        return new_df
