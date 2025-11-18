from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

import pandas
from annofabapi.parser import lazy_parse_simple_annotation_zip

logger = logging.getLogger(__name__)


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
        logger.debug(f"アノテーションZIPファイルから区間アノテーションの長さを計算します。 :: project_id='{project_id}', file='{annotation_zip!s}'")

        result: dict[tuple[str, str], float] = defaultdict(float)  # key:(project_id, task_id), value:合計アノテーション時間（分）

        for index, parser in enumerate(lazy_parse_simple_annotation_zip(annotation_zip)):
            simple_annotation = parser.load_json()

            total_duration = 0.0
            for detail in simple_annotation["details"]:
                # ラベルフィルタリングの処理
                if include_labels is not None:
                    if detail["label"] not in include_labels:
                        continue
                elif exclude_labels is not None and detail["label"] in exclude_labels:
                    continue

                # データ形式に応じてアノテーション時間を計算
                data = detail["data"]

                if data["_type"] == "Range":
                    # 区間アノテーションの場合
                    begin = data["begin"]
                    end = data["end"]
                    total_duration += (end - begin) / 1000.0 / 60.0  # ミリ秒から分に変換

            result[(project_id, parser.task_id)] += total_duration

            if (index + 1) % 10000 == 0:
                logger.debug(f"{index + 1}件のアノテーションJSONを読み込みました。 :: project_id='{project_id}', file='{annotation_zip!s}'")

        result_list = [(project_id, task_id, duration) for (project_id, task_id), duration in result.items()]

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
