from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas

from annofabcli.common.annotation_production_volume import aggregate_annotation_production_volume


class AnnotationCount:
    """
    アノテーション数が格納されたDataFrameをラップしたクラスです。

    DataFrameは`project_id`,`task_id`のペアがユニークなキーです。
    """

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "project_id",
            "task_id",
            "annotation_count",
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
    def from_annotation_zip(
        cls,
        annotation_zip: Path,
        project_id: str,
        *,
        get_annotation_count_func: Callable[[dict[str, Any]], int] | None = None,
        include_labels: list[str] | None = None,
        exclude_labels: list[str] | None = None,
    ) -> AnnotationCount:
        """
        アノテーションZIPファイルからインスタンスを生成します。

        Args:
            annotation_zip_file: アノテーションZIPファイルのパス
            project_id: プロジェクトID。DataFrameに格納するために使用します。
            get_annotation_count_func: アノテーション数を算出するための関数。
                引数はdict, 戻り値はintの関数です。未指定の場合は、detailsの数をアノテーション数になります。
            include_labels: 集計対象に含めるラベル名のリスト
            exclude_labels: 集計対象から除外するラベル名のリスト

        """
        volumes = aggregate_annotation_production_volume(
            annotation_zip,
            include_labels=include_labels,
            exclude_labels=exclude_labels,
            calculate_duration=False,
            get_annotation_count_func=get_annotation_count_func,
        )
        result = [(project_id, task_id, volume.annotation_count) for task_id, volume in volumes.items()]

        if len(result) == 0:
            return cls.empty()

        df = pandas.DataFrame(result, columns=["project_id", "task_id", "annotation_count"])
        return cls(df)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls) -> AnnotationCount:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "annotation_count": "int",
        }

        df = pandas.DataFrame(columns=cls.columns()).astype(df_dtype)
        return cls(df)
