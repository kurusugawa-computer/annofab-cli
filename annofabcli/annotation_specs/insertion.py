from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from annofabapi.util.annotation_specs import get_attribute_name_en, get_label_name_en


def get_insertion_index(names: Sequence[str], *, before_name: str | None, context: str) -> int:
    """英語名で指定した基準要素の直前の位置を返す。

    Args:
        names: 既存要素の英語名一覧
        before_name: 基準要素の英語名。未指定なら末尾
        context: エラーに表示する対象

    Returns:
        挿入位置

    Raises:
        ValueError: 基準要素が存在しない、または一意に特定できない場合
    """
    if before_name is None:
        return len(names)
    indices = [index for index, name in enumerate(names) if name == before_name]
    if len(indices) != 1:
        raise ValueError(f"{context}で基準名(英語)='{before_name}' を一意に特定できません。一致件数: {len(indices)}")
    return indices[0]


def resolve_before_attribute_id(
    annotation_specs: Mapping[str, Any],
    *,
    target_labels: Sequence[Mapping[str, Any]],
    before_attribute_name_en: str | None,
) -> str | None:
    """全対象ラベルに含まれる基準属性のIDを返す。

    Args:
        annotation_specs: 更新前のアノテーション仕様
        target_labels: 属性の追加先ラベル一覧
        before_attribute_name_en: 基準属性の英語名

    Returns:
        基準属性のID。位置未指定ならNone

    Raises:
        ValueError: 基準属性を一意に特定できない、または対象ラベルに含まれない場合
    """
    if before_attribute_name_en is None:
        return None
    attributes = annotation_specs["additionals"]
    index = get_insertion_index([get_attribute_name_en(attribute) for attribute in attributes], before_name=before_attribute_name_en, context="属性定義一覧")
    attribute_id: str = attributes[index]["additional_data_definition_id"]
    missing_labels = [get_label_name_en(label) for label in target_labels if attribute_id not in label["additional_data_definitions"]]
    if missing_labels:
        raise ValueError(f"対象ラベル {missing_labels} に基準属性(英語)='{before_attribute_name_en}' が含まれていません。")
    return attribute_id


def insert_attribute_into_labels(
    labels: Sequence[dict[str, Any]],
    *,
    target_label_ids: set[str],
    attribute_id: str,
    before_attribute_id: str | None,
) -> None:
    """対象ラベルの属性一覧に属性IDを挿入する。

    Args:
        labels: 更新するラベル一覧
        target_label_ids: 追加先のラベルID一覧
        attribute_id: 追加する属性ID
        before_attribute_id: 検証済みの基準属性ID。未指定なら末尾

    Returns:
        None
    """
    for label in labels:
        if label["label_id"] in target_label_ids:
            attribute_ids = label["additional_data_definitions"]
            index = len(attribute_ids) if before_attribute_id is None else attribute_ids.index(before_attribute_id)
            attribute_ids.insert(index, attribute_id)
