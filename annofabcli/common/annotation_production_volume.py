from __future__ import annotations

import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from annofabapi.parser import lazy_parse_simple_annotation_zip

logger = logging.getLogger(__name__)


@dataclass
class AnnotationProductionVolume:
    """タスクごとのアノテーション生産量。"""

    annotation_count: int = 0
    """アノテーション件数。"""
    annotation_duration_minute: float = 0.0
    """区間アノテーションの長さの合計（分）。"""


def aggregate_annotation_production_volume(
    annotation_zip: Path,
    *,
    task_ids: Collection[str] | None = None,
    include_labels: Collection[str] | None = None,
    exclude_labels: Collection[str] | None = None,
    calculate_duration: bool = True,
    get_annotation_count_func: Callable[[dict[str, Any]], int] | None = None,
) -> dict[str, AnnotationProductionVolume]:
    """ZIPを一度走査し、タスクごとの件数と区間長さを集計します。

    Args:
        annotation_zip: SimpleアノテーションZIP。
        task_ids: 対象タスクID。Noneなら全タスクを集計します。
        include_labels: 集計に含めるラベル名（英語）。
        exclude_labels: 集計から除外するラベル名（英語）。
        calculate_duration: 区間長さも集計するか。
        get_annotation_count_func: フィルター適用後のJSONから件数を計算する関数。

    Returns:
        タスクIDをキーとした生産量。JSONがないタスクは含みません。
    """
    target_ids = set(task_ids) if task_ids is not None else None
    included = set(include_labels) if include_labels is not None else None
    excluded = set(exclude_labels) if exclude_labels is not None else set()
    result: dict[str, AnnotationProductionVolume] = {}
    count = 0
    for parser in lazy_parse_simple_annotation_zip(annotation_zip):
        if target_ids is not None and parser.task_id not in target_ids:
            continue
        annotation = parser.load_json()
        details = [detail for detail in annotation["details"] if (detail["label"] in included if included is not None else detail["label"] not in excluded)]
        volume = result.setdefault(parser.task_id, AnnotationProductionVolume())
        if get_annotation_count_func is None:
            volume.annotation_count += len(details)
        else:
            volume.annotation_count += get_annotation_count_func({**annotation, "details": details})
        if calculate_duration:
            volume.annotation_duration_minute += sum((detail["data"]["end"] - detail["data"]["begin"]) / 60000 for detail in details if detail["data"]["_type"] == "Range")
        count += 1
        if count % 10000 == 0:
            logger.info(f"アノテーションJSONを{count}件集計しました。")
    logger.info(f"アノテーション生産量の集計が完了しました。JSON {count}件、タスク {len(result)}件。")
    return result
