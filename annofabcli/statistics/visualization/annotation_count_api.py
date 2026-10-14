from __future__ import annotations

import logging
from collections.abc import Collection, Iterable
from enum import Enum

import annofabapi
import pandas
from annofabapi.models import Task
from annofabapi.plugin import ThreeDimensionAnnotationType
from annofabapi.util.annotation_specs import get_label_name_en

from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount

logger = logging.getLogger(__name__)


class AnnotationCountSource(Enum):
    """生産量に使うアノテーション数の取得元。"""

    AUTO = "auto"
    """3Dセグメントの有無で自動判定する。"""
    ZIP = "zip"
    """アノテーションZIPから集計する。"""
    API = "api"
    """一覧APIから集計する。"""


def resolve_annotation_count_source(service: annofabapi.Resource, project_id: str, source: AnnotationCountSource) -> AnnotationCountSource:
    """アノテーション仕様から件数の取得元を決めます。

    Args:
        service: APIクライアント。
        project_id: プロジェクトID。
        source: 指定された取得元。

    Returns:
        自動判定を解決した取得元。
    """
    if source != AnnotationCountSource.AUTO:
        return source
    specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "3"})
    segment_types = {ThreeDimensionAnnotationType.INSTANCE_SEGMENT.value, ThreeDimensionAnnotationType.SEMANTIC_SEGMENT.value}
    if any(label["annotation_type"] in segment_types for label in specs["labels"]):
        logger.info(f"project_id='{project_id}' :: 3Dセグメントのラベルが含まれているため、アノテーション数を一覧APIから集計します。")
        return AnnotationCountSource.API
    return AnnotationCountSource.ZIP


def count_annotations_from_api(
    service: annofabapi.Resource,
    project_id: str,
    tasks: Iterable[Task],
    *,
    include_labels: Collection[str] | None = None,
    exclude_labels: Collection[str] | None = None,
) -> AnnotationCount:
    """一覧APIからタスクごとの件数を集計します。外部ファイルは取得しません。

    Args:
        service: APIクライアント。
        project_id: プロジェクトID。
        tasks: 集計対象タスク。
        include_labels: 含めるラベルの英語名。
        exclude_labels: 除外するラベルの英語名。

    Returns:
        アノテーションがないタスクも0件で含む集計値。
    """
    label_ids: list[str | None] = [None]
    if include_labels is not None or exclude_labels is not None:
        specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "3"})
        label_ids = sorted(
            {label["label_id"] for label in specs["labels"] if (get_label_name_en(label) in include_labels if include_labels is not None else get_label_name_en(label) not in (exclude_labels or []))}
        )

    def count(task_id: str, label_id: str | None) -> int:
        """最初のページの総件数を取得します。

        Args:
            task_id: タスクID。
            label_id: 絞り込むラベルID。Noneなら全ラベルを数えます。

        Returns:
            検索結果の総件数。over_limitは一覧の取得上限を表し、総件数は制限しません。
        """
        query: dict[str, str | bool] = {"task_id": task_id, "exact_match_task_id": True}
        if label_id is not None:
            query["label_id"] = label_id
        result, _ = service.api.get_annotation_list(
            project_id,
            query_params={"query": query, "page": 1, "limit": 1, "v": "2", "no_aggregate_label_and_input": True},
        )
        return int(result["total_count"])

    rows: list[tuple[str, str, int]] = []
    for index, task in enumerate(tasks, start=1):
        task_id = task["task_id"]
        logger.debug(f"project_id='{project_id}' :: {index}件目: タスク'{task_id}'のアノテーション数を集計します。")
        annotation_count = sum(count(task_id, label_id) for label_id in label_ids)
        rows.append((project_id, task_id, annotation_count))
        if index % 100 == 0:
            logger.info(f"project_id='{project_id}' :: {index}件のタスクのアノテーション数を集計しました。")
    logger.info(f"project_id='{project_id}' :: アノテーション数の集計が完了しました。成功{len(rows)}件。")
    return AnnotationCount(pandas.DataFrame(rows, columns=AnnotationCount.columns())) if rows else AnnotationCount.empty()
