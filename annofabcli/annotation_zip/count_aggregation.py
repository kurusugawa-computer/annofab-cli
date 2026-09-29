from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Collection, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from annofabcli.annotation_zip.task_metadata import TASK_METADATA_COLUMN_PREFIX

TASK_ID_GROUP = "task_id"
"""タスク単位の詳細出力を表す集計キー。"""

INPUT_DATA_ID_GROUP = "input_data_id"
"""入力データ単位の詳細出力を表す集計キー。"""

PROJECT_ID_GROUP = "project_id"
"""プロジェクト全体のサマリー出力を表す集計キー。"""

SUMMARY_GROUPS = frozenset({"task_phase", "task_phase_stage", "task_status"})
"""複数指定できる組み込みのサマリー集計キー。"""

EXCLUSIVE_GROUPS = frozenset({TASK_ID_GROUP, INPUT_DATA_ID_GROUP, PROJECT_ID_GROUP})
"""単独でのみ指定できる集計キー。"""

GroupValue = str | int | float | bool | None
GroupKey = tuple[tuple[type[object], GroupValue], ...]
"""値の型を区別する内部集計キー。"""

CountKey = TypeVar("CountKey", bound=Hashable)
TaskCountType = TypeVar("TaskCountType", bound="TaskCount")


class TaskCount(Protocol):
    """タスク単位の集計結果が持つプロパティ。"""

    @property
    def project_id(self) -> str: ...

    @property
    def task_id(self) -> str: ...

    @property
    def task_status(self) -> EnumValue: ...

    @property
    def task_phase(self) -> EnumValue: ...

    @property
    def task_phase_stage(self) -> int: ...

    @property
    def input_data_count(self) -> int: ...


class EnumValue(Protocol):
    """文字列値を持つ列挙型。"""

    @property
    def value(self) -> str: ...


@dataclass
class CountSummary:
    """任意のタスク項目でまとめたアノテーション数。"""

    group_values: dict[str, GroupValue]
    """集計キーと値。"""

    task_count: int = 0
    """グループに含まれるタスク数。"""

    input_data_count: int = 0
    """グループに含まれる入力データ数。"""

    annotation_count: int = 0
    """グループに含まれるアノテーション数。"""

    value_counts: Counter[Hashable] = field(default_factory=Counter)
    """ラベルまたは属性値ごとのアノテーション数。"""


def validate_group_by(group_by: Collection[str]) -> str | None:
    """集計キーの組み合わせを検証します。

    Args:
        group_by: 集計キー。

    Returns:
        不正な場合はエラーメッセージ、正しい場合はNone。
    """
    group_by_list = list(group_by)
    if not group_by_list:
        return "`--group_by`には1個以上の値を指定してください。"
    if len(group_by_list) != len(set(group_by_list)):
        return "`--group_by`に同じ値を複数指定できません。"

    invalid_groups = [value for value in group_by_list if value not in SUMMARY_GROUPS | EXCLUSIVE_GROUPS and not value.startswith(f"{TASK_METADATA_COLUMN_PREFIX}.")]
    if invalid_groups:
        return f"`--group_by`に指定できない値があります: {invalid_groups}"

    metadata_groups = [value for value in group_by_list if value.startswith(f"{TASK_METADATA_COLUMN_PREFIX}.")]
    if any(value == f"{TASK_METADATA_COLUMN_PREFIX}." for value in metadata_groups):
        return "タスクメタデータのキーは`task_metadata.<key>`形式で指定してください。"

    exclusive_groups = EXCLUSIVE_GROUPS.intersection(group_by_list)
    if exclusive_groups and len(group_by_list) > 1:
        return f"{sorted(exclusive_groups)}は他の集計キーと同時に指定できません。"
    return None


def is_summary_group(group_by: Collection[str]) -> bool:
    """サマリー集計かどうかを返します。

    Args:
        group_by: 集計キー。

    Returns:
        サマリー集計の場合はTrue。
    """
    return list(group_by) not in [[TASK_ID_GROUP], [INPUT_DATA_ID_GROUP]]


def needs_task_metadata(group_by: Collection[str]) -> bool:
    """集計にタスクメタデータが必要かどうかを返します。

    Args:
        group_by: 集計キー。

    Returns:
        タスクメタデータが必要な場合はTrue。
    """
    return any(value.startswith(f"{TASK_METADATA_COLUMN_PREFIX}.") for value in group_by)


def aggregate_task_counts(
    task_counts: Iterable[TaskCountType],
    group_by: Collection[str],
    *,
    value_counts_getter: Callable[[TaskCountType], Mapping[CountKey, int]],
    annotation_count_getter: Callable[[TaskCountType], int] | None = None,
    task_metadata_by_task_id: Mapping[str, Mapping[str, object]] | None = None,
) -> list[CountSummary]:
    """タスク単位の結果を指定項目ごとに集計します。

    Args:
        task_counts: タスク単位の集計結果。
        group_by: 集計キー。
        value_counts_getter: ラベルまたは属性値ごとの件数を取得する関数。
        annotation_count_getter: アノテーション総数を取得する関数。
        task_metadata_by_task_id: タスクIDごとのメタデータ。

    Returns:
        指定項目ごとの集計結果。
    """
    group_by_list = list(group_by)
    summary_by_key: dict[GroupKey, CountSummary] = {}
    for task_count in task_counts:
        group_values = _get_group_values(task_count, group_by_list, task_metadata_by_task_id or {})
        key: GroupKey = tuple((type(value), value) for value in group_values.values())
        summary = summary_by_key.setdefault(key, CountSummary(group_values=group_values))
        summary.task_count += 1
        summary.input_data_count += task_count.input_data_count
        if annotation_count_getter is not None:
            summary.annotation_count += annotation_count_getter(task_count)
        summary.value_counts.update(value_counts_getter(task_count))
    return list(summary_by_key.values())


def _get_group_values(
    task_count: TaskCount,
    group_by: Collection[str],
    task_metadata_by_task_id: Mapping[str, Mapping[str, object]],
) -> dict[str, GroupValue]:
    """タスクから集計キーに対応する値を取得します。

    Args:
        task_count: タスク単位の集計結果。
        group_by: 集計キー。
        task_metadata_by_task_id: タスクIDごとのメタデータ。

    Returns:
        集計キーと値の辞書。
    """
    result: dict[str, GroupValue] = {}
    for field_name in group_by:
        if field_name == PROJECT_ID_GROUP:
            value: object = task_count.project_id
        elif field_name == "task_phase":
            value = task_count.task_phase.value
        elif field_name == "task_phase_stage":
            value = task_count.task_phase_stage
        elif field_name == "task_status":
            value = task_count.task_status.value
        elif field_name.startswith(f"{TASK_METADATA_COLUMN_PREFIX}."):
            metadata_key = field_name.removeprefix(f"{TASK_METADATA_COLUMN_PREFIX}.")
            value = task_metadata_by_task_id.get(task_count.task_id, {}).get(metadata_key)
        else:
            raise ValueError(f"サマリー集計ではサポートされていない集計キーです: {field_name}")
        result[field_name] = _normalize_group_value(value)
    return result


def _normalize_group_value(value: object) -> GroupValue:
    """集計キーの値をハッシュ可能かつ出力可能な値へ変換します。

    Args:
        value: タスク情報またはタスクメタデータの値。

    Returns:
        正規化した値。辞書や配列はJSON文字列。
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
