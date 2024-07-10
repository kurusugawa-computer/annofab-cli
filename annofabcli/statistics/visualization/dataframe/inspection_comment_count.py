from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import pandas
from annofabapi.models import CommentStatus, TaskPhase

logger = logging.getLogger(__name__)


class InspectionCommentCount:
    """
    検査コメント数が格納されたDataFrameをラップしたクラスです。

    DataFrameは`project_id`,`task_id`のペアがユニークなキーです。
    """

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "project_id",
            "task_id",
            "inspection_comment_count",
            "inspection_comment_count_in_inspection_phase",
            "inspection_comment_count_in_acceptance_phase",
        ]

    @classmethod
    def required_columns_exist(cls, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(cls.columns()) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns()}の列が必要です。 :: {df.columns=}")
        self.df = df

    @classmethod
    def from_api_content(cls, comment_list: list[dict[str, Any]]) -> InspectionCommentCount:
        """
        APIから取得したコメント情報からインスタンスを生成します。

        Args:
            inspection_comment_list: 検査コメントのリスト

        """

        def is_target_comment(comment: dict[str, Any]) -> bool:
            """
            以下のすべての条件を満たすコメントかどうか
            * 検査コメント
            * 返信コメントでない（最初のコメント）
            * 解決済のコメント
            """
            if comment["comment_type"] != "inspection":
                return False

            comment_node = comment["comment_node"]
            if comment_node["_type"] != "Root":
                return False

            if comment_node["status"] != CommentStatus.RESOLVED.value:  # noqa: SIM103
                return False
            return True

        result: dict[tuple[str, str, str], int] = defaultdict(int)  # key: (project_id, task_id, phase), value: 検査コメント数

        for comment in comment_list:
            if is_target_comment(comment):
                result[(comment["project_id"], comment["task_id"], comment["phase"])] += 1

        if len(result) == 0:
            return cls.empty()

        result2 = [(project_id, task_id, phase, count) for (project_id, task_id, phase), count in result.items()]
        df = pandas.DataFrame(result2, columns=["project_id", "task_id", "phase", "count"])
        df = df.pivot_table(index=["project_id", "task_id"], columns="phase", values="count", fill_value=0)
        if TaskPhase.INSPECTION.value not in df.columns:
            df[TaskPhase.INSPECTION.value] = 0
        if TaskPhase.ACCEPTANCE.value not in df.columns:
            df[TaskPhase.ACCEPTANCE.value] = 0

        df = df.rename(
            columns={
                TaskPhase.INSPECTION.value: "inspection_comment_count_in_inspection_phase",
                TaskPhase.ACCEPTANCE.value: "inspection_comment_count_in_acceptance_phase",
            }
        )
        df["inspection_comment_count"] = df["inspection_comment_count_in_inspection_phase"] + df["inspection_comment_count_in_acceptance_phase"]
        df = df.reset_index()
        return cls(df)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls) -> InspectionCommentCount:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "inspection_comment_count": "int",
            "inspection_comment_count_in_inspection_phase": "int",
            "inspection_comment_count_in_acceptance_phase": "int",
        }

        df = pandas.DataFrame(columns=cls.columns()).astype(df_dtype)
        return cls(df)
