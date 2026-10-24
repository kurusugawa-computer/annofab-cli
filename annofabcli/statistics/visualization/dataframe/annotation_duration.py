from __future__ import annotations

from pathlib import Path

import pandas

from annofabcli.common.annotation_production_volume import aggregate_annotation_production_volume


class AnnotationDuration:
    """
    アノテーション時間が格納されたDataFrameをラップしたクラスです。

    DataFrameは`project_id`,`task_id`のペアがユニークなキーです。
    """

    @classmethod
    def columns(cls) -> list[str]:
        return [
            "project_id",
            "task_id",
            "annotation_duration_minute",
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
        include_labels: list[str] | None = None,
        exclude_labels: list[str] | None = None,
    ) -> AnnotationDuration:
        """
        アノテーションZIPファイルからインスタンスを生成します。

        Args:
            annotation_zip: アノテーションZIPファイルのパス
            project_id: プロジェクトID。DataFrameに格納するために使用します。
            include_labels: 集計対象に含めるラベル名のリスト
            exclude_labels: 集計対象から除外するラベル名のリスト

        """
        volumes = aggregate_annotation_production_volume(annotation_zip, include_labels=include_labels, exclude_labels=exclude_labels)
        result_list = [(project_id, task_id, volume.annotation_duration_minute) for task_id, volume in volumes.items()]

        if len(result_list) == 0:
            return cls.empty()

        df = pandas.DataFrame(result_list, columns=cls.columns())
        return cls(df)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls) -> AnnotationDuration:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[str, str] = {
            "project_id": "string",
            "task_id": "string",
            "annotation_duration_minute": "float64",
        }

        df = pandas.DataFrame(columns=cls.columns()).astype(df_dtype)
        return cls(df)
