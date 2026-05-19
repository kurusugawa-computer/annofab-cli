from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from annofabapi.util.annotation_specs import get_message_with_lang

from annofabcli.annotation_specs.diff_models import (
    AnnotationSpecsDiff,
    AttributeRestrictionDiffItem,
    AttributeRestrictionsDiff,
    AttributesDiff,
    ChangedAttribute,
    ChangedAttributeRestriction,
    ChangedChoice,
    ChangedLabel,
    JsonValue,
    LabelsDiff,
)


def _get_added_ids(left_ids: Sequence[str], right_ids: Sequence[str]) -> list[str]:
    """追加されたID一覧を取得する。

    Args:
        left_ids: 比較元のID一覧。
        right_ids: 比較先のID一覧。

    Returns:
        比較先にのみ存在するID一覧。
    """
    left_ids_set = set(left_ids)
    return [e for e in right_ids if e not in left_ids_set]


def _get_removed_ids(left_ids: Sequence[str], right_ids: Sequence[str]) -> list[str]:
    """削除されたID一覧を取得する。

    Args:
        left_ids: 比較元のID一覧。
        right_ids: 比較先のID一覧。

    Returns:
        比較元にのみ存在するID一覧。
    """
    right_ids_set = set(right_ids)
    return [e for e in left_ids if e not in right_ids_set]


def _is_order_changed(left_ids: Sequence[str], right_ids: Sequence[str]) -> bool:
    """同一要素の並び順が変更されたかどうかを返す。

    Args:
        left_ids: 比較元のID一覧。
        right_ids: 比較先のID一覧。

    Returns:
        要素集合が同じで順序だけが異なる場合は ``True`` 。
    """
    return set(left_ids) == set(right_ids) and list(left_ids) != list(right_ids)


def _to_json_text(value: JsonValue) -> str:
    """JSON値を安定した文字列に変換する。

    Args:
        value: 文字列化するJSON値。

    Returns:
        キー順を固定したJSON文字列。
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _create_attribute_restriction_diff_item(restriction: dict[str, Any]) -> AttributeRestrictionDiffItem:
    """属性制約の差分項目を生成する。

    Args:
        restriction: 属性制約情報。

    Returns:
        属性制約差分項目。
    """
    return AttributeRestrictionDiffItem(condition=restriction["condition"])


def _to_attribute_restriction_key(restriction: dict[str, Any]) -> str:
    """属性制約を比較用のキー文字列に変換する。

    Args:
        restriction: 属性制約情報。

    Returns:
        属性制約の識別に使う文字列。
    """

    def _normalize_condition_value(value: JsonValue, *, key: str | None = None) -> JsonValue:
        """属性制約の条件値を比較用に正規化する。

        Args:
            value: 正規化する属性制約の条件値。
            key: 親要素のキー名。

        Returns:
            比較しやすい形に正規化した条件値。
        """
        if isinstance(value, dict):
            return {k: _normalize_condition_value(v, key=k) for k, v in sorted(value.items())}
        if isinstance(value, list):
            normalized_list = [_normalize_condition_value(e) for e in value]
            if key == "labels":
                # HasLabel.labels は集合として扱うため、ラベルIDの順序差は無視する。
                return sorted(normalized_list, key=_to_json_text)
            return normalized_list
        return value

    return _to_json_text(
        {
            "additional_data_definition_id": restriction["additional_data_definition_id"],
            "condition": _normalize_condition_value(restriction["condition"]),
        }
    )


def _get_added_restrictions(
    left_restrictions: Sequence[dict[str, Any]],
    right_restrictions: Sequence[dict[str, Any]],
) -> list[AttributeRestrictionDiffItem]:
    """追加された属性制約一覧を取得する。

    Args:
        left_restrictions: 比較元の属性制約一覧。
        right_restrictions: 比較先の属性制約一覧。

    Returns:
        比較先にのみ存在する属性制約差分項目一覧。
    """
    left_counter = Counter(_to_attribute_restriction_key(e) for e in left_restrictions)
    added_restrictions = []
    for restriction in right_restrictions:
        key = _to_attribute_restriction_key(restriction)
        if left_counter[key] > 0:
            left_counter[key] -= 1
            continue
        added_restrictions.append(_create_attribute_restriction_diff_item(restriction))
    return added_restrictions


def _get_removed_restrictions(
    left_restrictions: Sequence[dict[str, Any]],
    right_restrictions: Sequence[dict[str, Any]],
) -> list[AttributeRestrictionDiffItem]:
    """削除された属性制約一覧を取得する。

    Args:
        left_restrictions: 比較元の属性制約一覧。
        right_restrictions: 比較先の属性制約一覧。

    Returns:
        比較元にのみ存在する属性制約差分項目一覧。
    """
    right_counter = Counter(_to_attribute_restriction_key(e) for e in right_restrictions)
    removed_restrictions = []
    for restriction in left_restrictions:
        key = _to_attribute_restriction_key(restriction)
        if right_counter[key] > 0:
            right_counter[key] -= 1
            continue
        removed_restrictions.append(_create_attribute_restriction_diff_item(restriction))
    return removed_restrictions


def compare_choice(left_choice: dict[str, Any], right_choice: dict[str, Any]) -> ChangedChoice | None:
    """選択肢差分を比較する。

    Args:
        left_choice: 比較元の選択肢情報。
        right_choice: 比較先の選択肢情報。

    Returns:
        差分がある場合は選択肢差分、ない場合は ``None`` 。
    """
    diff = ChangedChoice(
        choice_id=right_choice["choice_id"],
        name_ja_changed=get_message_with_lang(left_choice["name"], "ja-JP") != get_message_with_lang(right_choice["name"], "ja-JP"),
        name_en_changed=get_message_with_lang(left_choice["name"], "en-US") != get_message_with_lang(right_choice["name"], "en-US"),
        name_vi_changed=get_message_with_lang(left_choice["name"], "vi-VN") != get_message_with_lang(right_choice["name"], "vi-VN"),
        keybind_changed=left_choice["keybind"] != right_choice["keybind"],
    )
    if not diff.has_changes():
        return None
    return diff


def compare_attribute(left_attribute: dict[str, Any], right_attribute: dict[str, Any]) -> ChangedAttribute | None:
    """属性差分を比較する。

    Args:
        left_attribute: 比較元の属性情報。
        right_attribute: 比較先の属性情報。

    Returns:
        差分がある場合は属性差分、ない場合は ``None`` 。
    """
    left_choice_list = left_attribute["choices"]
    right_choice_list = right_attribute["choices"]
    left_choice_ids = [e["choice_id"] for e in left_choice_list]
    right_choice_ids = [e["choice_id"] for e in right_choice_list]
    left_choice_dict = {e["choice_id"]: e for e in left_choice_list}
    right_choice_dict = {e["choice_id"]: e for e in right_choice_list}
    changed_choices = []
    for choice_id in right_choice_ids:
        if choice_id not in left_choice_dict:
            continue
        changed_choice = compare_choice(left_choice_dict[choice_id], right_choice_dict[choice_id])
        if changed_choice is not None:
            changed_choices.append(changed_choice)

    added_choice_ids = _get_added_ids(left_choice_ids, right_choice_ids)
    removed_choice_ids = _get_removed_ids(left_choice_ids, right_choice_ids)
    choices_order_changed = _is_order_changed(left_choice_ids, right_choice_ids)

    diff = ChangedAttribute(
        attribute_id=right_attribute["additional_data_definition_id"],
        read_only_changed=left_attribute["read_only"] != right_attribute["read_only"],
        name_ja_changed=get_message_with_lang(left_attribute["name"], "ja-JP") != get_message_with_lang(right_attribute["name"], "ja-JP"),
        name_en_changed=get_message_with_lang(left_attribute["name"], "en-US") != get_message_with_lang(right_attribute["name"], "en-US"),
        name_vi_changed=get_message_with_lang(left_attribute["name"], "vi-VN") != get_message_with_lang(right_attribute["name"], "vi-VN"),
        keybind_changed=left_attribute["keybind"] != right_attribute["keybind"],
        type_changed=left_attribute["type"] != right_attribute["type"],
        default_changed=left_attribute["default"] != right_attribute["default"],
        metadata_changed=left_attribute["metadata"] != right_attribute["metadata"],
        choices_order_changed=choices_order_changed,
        added_choice_ids=added_choice_ids,
        removed_choice_ids=removed_choice_ids,
        changed_choices=changed_choices,
    )
    if not diff.has_changes():
        return None
    return diff


def compare_attributes(left_specs: dict[str, Any], right_specs: dict[str, Any]) -> AttributesDiff:
    """属性一覧の差分を比較する。

    Args:
        left_specs: 比較元のアノテーション仕様。
        right_specs: 比較先のアノテーション仕様。

    Returns:
        属性一覧の差分。
    """
    left_attribute_list = left_specs["additionals"]
    right_attribute_list = right_specs["additionals"]
    left_attribute_ids = [e["additional_data_definition_id"] for e in left_attribute_list]
    right_attribute_ids = [e["additional_data_definition_id"] for e in right_attribute_list]
    left_attribute_dict = {e["additional_data_definition_id"]: e for e in left_attribute_list}
    right_attribute_dict = {e["additional_data_definition_id"]: e for e in right_attribute_list}

    changed_attributes = []
    for attribute_id in right_attribute_ids:
        if attribute_id not in left_attribute_dict:
            continue
        changed_attribute = compare_attribute(left_attribute_dict[attribute_id], right_attribute_dict[attribute_id])
        if changed_attribute is not None:
            changed_attributes.append(changed_attribute)

    return AttributesDiff(
        added_attribute_ids=_get_added_ids(left_attribute_ids, right_attribute_ids),
        removed_attribute_ids=_get_removed_ids(left_attribute_ids, right_attribute_ids),
        changed_attributes=changed_attributes,
    )


def compare_label(left_label: dict[str, Any], right_label: dict[str, Any]) -> ChangedLabel | None:
    """ラベル差分を比較する。

    Args:
        left_label: 比較元のラベル情報。
        right_label: 比較先のラベル情報。

    Returns:
        差分がある場合はラベル差分、ない場合は ``None`` 。
    """
    left_attribute_ids = left_label["additional_data_definitions"]
    right_attribute_ids = right_label["additional_data_definitions"]
    added_attribute_ids = _get_added_ids(left_attribute_ids, right_attribute_ids)
    removed_attribute_ids = _get_removed_ids(left_attribute_ids, right_attribute_ids)
    attributes_order_changed = _is_order_changed(left_attribute_ids, right_attribute_ids)

    diff = ChangedLabel(
        label_id=right_label["label_id"],
        color_changed=left_label["color"] != right_label["color"],
        keybind_changed=left_label["keybind"] != right_label["keybind"],
        label_name_ja_changed=get_message_with_lang(left_label["label_name"], "ja-JP") != get_message_with_lang(right_label["label_name"], "ja-JP"),
        label_name_en_changed=get_message_with_lang(left_label["label_name"], "en-US") != get_message_with_lang(right_label["label_name"], "en-US"),
        label_name_vi_changed=get_message_with_lang(left_label["label_name"], "vi-VN") != get_message_with_lang(right_label["label_name"], "vi-VN"),
        attributes_order_changed=attributes_order_changed,
        added_attribute_ids=added_attribute_ids,
        removed_attribute_ids=removed_attribute_ids,
        field_values_changed=left_label["field_values"] != right_label["field_values"],
        metadata_changed=left_label["metadata"] != right_label["metadata"],
        annotation_type_changed=left_label["annotation_type"] != right_label["annotation_type"],
    )
    if not diff.has_changes():
        return None
    return diff


def compare_labels(left_specs: dict[str, Any], right_specs: dict[str, Any]) -> LabelsDiff:
    """ラベル一覧の差分を比較する。

    Args:
        left_specs: 比較元のアノテーション仕様。
        right_specs: 比較先のアノテーション仕様。

    Returns:
        ラベル一覧の差分。
    """
    left_label_list = left_specs["labels"]
    right_label_list = right_specs["labels"]
    left_label_ids = [e["label_id"] for e in left_label_list]
    right_label_ids = [e["label_id"] for e in right_label_list]
    left_label_dict = {e["label_id"]: e for e in left_label_list}
    right_label_dict = {e["label_id"]: e for e in right_label_list}

    changed_labels = []
    for label_id in right_label_ids:
        if label_id not in left_label_dict:
            continue
        changed_label = compare_label(left_label_dict[label_id], right_label_dict[label_id])
        if changed_label is not None:
            changed_labels.append(changed_label)

    return LabelsDiff(
        label_order_changed=_is_order_changed(left_label_ids, right_label_ids),
        added_label_ids=_get_added_ids(left_label_ids, right_label_ids),
        removed_label_ids=_get_removed_ids(left_label_ids, right_label_ids),
        changed_labels=changed_labels,
    )


def compare_attribute_restrictions(left_specs: dict[str, Any], right_specs: dict[str, Any]) -> AttributeRestrictionsDiff:
    """属性制約一覧の差分を比較する。

    Args:
        left_specs: 比較元のアノテーション仕様。
        right_specs: 比較先のアノテーション仕様。

    Returns:
        属性制約一覧の差分。
    """
    left_restrictions = left_specs["restrictions"]
    right_restrictions = right_specs["restrictions"]
    left_attribute_ids = [e["additional_data_definition_id"] for e in left_restrictions]
    right_attribute_ids = [e["additional_data_definition_id"] for e in right_restrictions]
    attribute_ids = list(dict.fromkeys([*right_attribute_ids, *left_attribute_ids]))
    changed_attribute_restrictions = []

    for attribute_id in attribute_ids:
        left_target_restrictions = [e for e in left_restrictions if e["additional_data_definition_id"] == attribute_id]
        right_target_restrictions = [e for e in right_restrictions if e["additional_data_definition_id"] == attribute_id]
        changed_attribute_restriction = ChangedAttributeRestriction(
            attribute_id=attribute_id,
            added_restrictions=_get_added_restrictions(left_target_restrictions, right_target_restrictions),
            removed_restrictions=_get_removed_restrictions(left_target_restrictions, right_target_restrictions),
        )
        if changed_attribute_restriction.has_changes():
            changed_attribute_restrictions.append(changed_attribute_restriction)

    return AttributeRestrictionsDiff(changed_attribute_restrictions=changed_attribute_restrictions)


def create_annotation_specs_diff(
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    *,
    targets: Iterable[str] | None = None,
) -> AnnotationSpecsDiff:
    """アノテーション仕様の差分を生成する。

    Args:
        left_specs: 比較元のアノテーション仕様。
        right_specs: 比較先のアノテーション仕様。
        targets: 差分生成の対象一覧。 ``None`` の場合は全対象を比較する。

    Returns:
        アノテーション仕様全体の差分。
    """
    target_set = set(targets) if targets is not None else {"labels", "attributes", "attribute_restrictions"}

    return AnnotationSpecsDiff(
        labels=compare_labels(left_specs, right_specs) if "labels" in target_set else None,
        attributes=compare_attributes(left_specs, right_specs) if "attributes" in target_set else None,
        attribute_restrictions=compare_attribute_restrictions(left_specs, right_specs) if "attribute_restrictions" in target_set else None,
    )
