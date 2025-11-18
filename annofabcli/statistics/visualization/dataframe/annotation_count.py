from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas
from annofabapi.parser import lazy_parse_simple_annotation_zip

logger = logging.getLogger(__name__)


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
        logger.debug(f"アノテーションZIPファイルを読み込みます。 :: project_id='{project_id}', file='{annotation_zip!s}'")

        def get_annotation_count_default(simple_annotation: dict[str, Any]) -> int:
            return len(simple_annotation["details"])

        def get_annotation_count_with_filter(simple_annotation: dict[str, Any]) -> int:
            details = simple_annotation["details"]

            if include_labels is not None:
                details = [d for d in details if d["label"] in include_labels]
            elif exclude_labels is not None:
                details = [d for d in details if d["label"] not in exclude_labels]

            if get_annotation_count_func is not None:
                # カスタム関数にフィルタ済みのdetailsを渡すため、一時的にsimple_annotationを変更
                filtered_annotation = simple_annotation.copy()
                filtered_annotation["details"] = details
                return get_annotation_count_func(filtered_annotation)
            else:
                return len(details)

        get_annotation_count: Callable[[dict[str, Any]], int]
        if include_labels is not None or exclude_labels is not None:
            get_annotation_count = get_annotation_count_with_filter
        elif get_annotation_count_func is not None:
            get_annotation_count = get_annotation_count_func
        else:
            get_annotation_count = get_annotation_count_default

        result: dict[tuple[str, str], int] = defaultdict(int)  # key:project_id,task_id, value:アノテーション数
        for index, parser in enumerate(lazy_parse_simple_annotation_zip(annotation_zip)):
            simple_annotation: dict[str, Any] = parser.load_json()
            annotation_count = get_annotation_count(simple_annotation)
            result[(project_id, parser.task_id)] += annotation_count
            if (index + 1) % 10000 == 0:
                logger.debug(f"{index + 1}件のアノテーションJSONを読み込みました。 :: project_id='{project_id}', file='{annotation_zip!s}'")

        result2 = [(project_id, task_id, count) for (project_id, task_id), count in result.items()]

        if len(result) == 0:
            return cls.empty()

        df = pandas.DataFrame(result2, columns=["project_id", "task_id", "annotation_count"])
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
