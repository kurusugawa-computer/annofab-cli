from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas

TASK_METADATA_COLUMN_PREFIX = "task_metadata"
"""タスクメタデータを表すCSV列名の接頭辞。"""


def get_task_metadata_by_task_id(
    task_json_path: Path,
) -> dict[str, dict[str, Any]]:
    """タスク全件ファイルからメタデータをタスクIDごとに取得する。

    Args:
        task_json_path: タスク全件ファイルのパス。

    Returns:
        タスクIDをキー、メタデータを値とする辞書。
    """
    with task_json_path.open(encoding="utf-8") as f:
        task_list: list[Mapping[str, Any]] = json.load(f)

    return {task["task_id"]: task.get("metadata", {}) for task in task_list}


def get_task_metadata_keys(task_metadata_by_task_id: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """CSVに出力するタスクメタデータのキーを返す。

    Args:
        task_metadata_by_task_id: タスクIDごとのメタデータ。

    Returns:
        すべてのタスクメタデータキーを昇順に並べたリスト。
    """
    return sorted({key for metadata in task_metadata_by_task_id.values() for key in metadata})


def add_task_metadata_to_dataframe(
    df: pandas.DataFrame,
    task_metadata_by_task_id: Mapping[str, Mapping[str, Any]],
) -> pandas.DataFrame:
    """タスクメタデータ列をDataFrameへ追加する。

    Args:
        df: ``task_id`` 列を持つDataFrame。
        task_metadata_by_task_id: タスクIDごとのメタデータ。

    Returns:
        タスクメタデータ列を追加したDataFrame。
    """
    metadata_keys = get_task_metadata_keys(task_metadata_by_task_id)
    result = df.copy()
    task_id_index = result.columns.get_loc("task_id")
    for index, key in enumerate(metadata_keys):
        result.insert(
            task_id_index + index + 1,
            f"{TASK_METADATA_COLUMN_PREFIX}.{key}",
            [task_metadata_by_task_id.get(task_id, {}).get(key) for task_id in result["task_id"]],
        )
    return result


def add_task_metadata_to_dict_list(
    item_list: list[dict[str, Any]],
    task_metadata_by_task_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """タスクメタデータを辞書のリストへ追加する。

    Args:
        item_list: ``task_id`` キーを持つ辞書のリスト。
        task_metadata_by_task_id: タスクIDごとのメタデータ。

    Returns:
        ``task_metadata`` キーを追加した辞書のリスト。
    """
    return [{**item, "task_metadata": dict(task_metadata_by_task_id.get(item["task_id"], {}))} for item in item_list]
