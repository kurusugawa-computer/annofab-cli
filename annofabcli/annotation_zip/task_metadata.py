from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

TASK_METADATA_COLUMN_PREFIX = "task_metadata"
"""タスクメタデータを表すCSV列名の接頭辞。"""


def get_task_metadata_by_task_id(
    task_json_path: Path,
    task_metadata_keys: Collection[str],
) -> dict[str, dict[str, Any]]:
    """タスク全件ファイルから指定されたメタデータをタスクIDごとに取得する。

    Args:
        task_json_path: タスク全件ファイルのパス。
        task_metadata_keys: 出力対象とするタスクメタデータのキー。

    Returns:
        タスクIDをキー、指定されたタスクメタデータを値とする辞書。
    """
    with task_json_path.open(encoding="utf-8") as f:
        task_list: list[Mapping[str, Any]] = json.load(f)

    return {task["task_id"]: {key: task.get("metadata", {}).get(key) for key in task_metadata_keys} for task in task_list}
