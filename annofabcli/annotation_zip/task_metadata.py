from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
