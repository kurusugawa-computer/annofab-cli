from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class AnnotationSpecsDiffOutputFormat(Enum):
    """`annotation_specs diff` の出力フォーマット。"""

    TEXT = "text"
    DETAIL_TEXT = "detail_text"
    JSON = "json"
    PRETTY_JSON = "pretty_json"


class ChangedChoice(BaseModel):
    """変更された選択肢の差分。"""

    model_config = ConfigDict(frozen=True)

    choice_id: str
    """選択肢ID"""
    name_ja_changed: bool = False
    """日本語名が変更されたか"""
    name_en_changed: bool = False
    """英語名が変更されたか"""
    name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.name_ja_changed,
                self.name_en_changed,
                self.name_vi_changed,
                self.keybind_changed,
            ]
        )


class ChangedAttribute(BaseModel):
    """変更された属性の差分。"""

    model_config = ConfigDict(frozen=True)

    attribute_id: str
    """属性ID"""
    read_only_changed: bool = False
    """read_only が変更されたか"""
    name_ja_changed: bool = False
    """日本語名が変更されたか"""
    name_en_changed: bool = False
    """英語名が変更されたか"""
    name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""
    type_changed: bool = False
    """属性型が変更されたか"""
    default_changed: bool = False
    """デフォルト値が変更されたか"""
    metadata_changed: bool = False
    """metadata が変更されたか"""
    choices_changed: bool = False
    """選択肢に変更があるか"""
    choices_order_changed: bool = False
    """選択肢の順序が変更されたか"""
    added_choice_ids: list[str] = Field(default_factory=list)
    """追加された選択肢ID一覧"""
    removed_choice_ids: list[str] = Field(default_factory=list)
    """削除された選択肢ID一覧"""
    changed_choices: list[ChangedChoice] = Field(default_factory=list)
    """変更された既存選択肢の差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.read_only_changed,
                self.name_ja_changed,
                self.name_en_changed,
                self.name_vi_changed,
                self.keybind_changed,
                self.type_changed,
                self.default_changed,
                self.metadata_changed,
                self.choices_changed,
                self.choices_order_changed,
                len(self.added_choice_ids) > 0,
                len(self.removed_choice_ids) > 0,
                len(self.changed_choices) > 0,
            ]
        )


class AttributesDiff(BaseModel):
    """属性一覧の差分。"""

    model_config = ConfigDict(frozen=True)

    attribute_order_changed: bool = False
    """属性全体の順序が変更されたか"""
    added_attribute_ids: list[str] = Field(default_factory=list)
    """追加された属性ID一覧"""
    removed_attribute_ids: list[str] = Field(default_factory=list)
    """削除された属性ID一覧"""
    changed_attributes: list[ChangedAttribute] = Field(default_factory=list)
    """変更された既存属性の差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.attribute_order_changed,
                len(self.added_attribute_ids) > 0,
                len(self.removed_attribute_ids) > 0,
                len(self.changed_attributes) > 0,
            ]
        )


class ChangedLabel(BaseModel):
    """変更されたラベルの差分。"""

    model_config = ConfigDict(frozen=True)

    label_id: str
    """ラベルID"""
    color_changed: bool = False
    """色が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""
    label_name_ja_changed: bool = False
    """日本語名が変更されたか"""
    label_name_en_changed: bool = False
    """英語名が変更されたか"""
    label_name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    attributes_changed: bool = False
    """紐づく属性に変更があるか"""
    attributes_order_changed: bool = False
    """紐づく属性の順序が変更されたか"""
    added_attribute_ids: list[str] = Field(default_factory=list)
    """追加された属性ID一覧"""
    removed_attribute_ids: list[str] = Field(default_factory=list)
    """削除された属性ID一覧"""
    field_values_changed: bool = False
    """field_values が変更されたか"""
    metadata_changed: bool = False
    """metadata が変更されたか"""
    annotation_type_changed: bool = False
    """annotation_type が変更されたか"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.color_changed,
                self.keybind_changed,
                self.label_name_ja_changed,
                self.label_name_en_changed,
                self.label_name_vi_changed,
                self.attributes_changed,
                self.attributes_order_changed,
                len(self.added_attribute_ids) > 0,
                len(self.removed_attribute_ids) > 0,
                self.field_values_changed,
                self.metadata_changed,
                self.annotation_type_changed,
            ]
        )


class LabelsDiff(BaseModel):
    """ラベル一覧の差分。"""

    model_config = ConfigDict(frozen=True)

    label_order_changed: bool = False
    """ラベル全体の順序が変更されたか"""
    added_label_ids: list[str] = Field(default_factory=list)
    """追加されたラベルID一覧"""
    removed_label_ids: list[str] = Field(default_factory=list)
    """削除されたラベルID一覧"""
    changed_labels: list[ChangedLabel] = Field(default_factory=list)
    """変更された既存ラベルの差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.label_order_changed,
                len(self.added_label_ids) > 0,
                len(self.removed_label_ids) > 0,
                len(self.changed_labels) > 0,
            ]
        )


class AnnotationSpecsDiff(BaseModel):
    """アノテーション仕様の差分。"""

    model_config = ConfigDict(frozen=True)

    labels: LabelsDiff | None = None
    """ラベル差分"""
    attributes: AttributesDiff | None = None
    """属性差分"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.labels is not None and self.labels.has_changes(),
                self.attributes is not None and self.attributes.has_changes(),
            ]
        )


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _get_message_by_lang(message_dict: dict[str, Any], lang: str) -> str | None:
    for message in message_dict.get("messages", []):
        if message.get("lang") == lang:
            return message.get("message")
    return None


def _get_added_ids(left_ids: Sequence[str], right_ids: Sequence[str]) -> list[str]:
    left_ids_set = set(left_ids)
    return [e for e in right_ids if e not in left_ids_set]


def _get_removed_ids(left_ids: Sequence[str], right_ids: Sequence[str]) -> list[str]:
    right_ids_set = set(right_ids)
    return [e for e in left_ids if e not in right_ids_set]


def _is_order_changed(left_ids: Sequence[str], right_ids: Sequence[str]) -> bool:
    return set(left_ids) == set(right_ids) and list(left_ids) != list(right_ids)


def _to_json_text(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _append_detail_line(
    lines: list[str],
    *,
    indent: str,
    name: str,
    changed: bool,
    left_value: JsonValue,
    right_value: JsonValue,
) -> None:
    if not changed:
        return
    lines.append(f"{indent}{name}: {_to_json_text(left_value)} -> {_to_json_text(right_value)}")


def _append_id_lines(lines: list[str], *, indent: str, label: str, values: Sequence[str]) -> None:
    if len(values) == 0:
        return
    lines.append(f"{indent}{label}:")
    lines.extend([f"{indent}- {value}" for value in values])


def _get_label_name_en_by_id(specs: dict[str, Any], label_id: str) -> str:
    label = next((e for e in specs.get("labels", []) if e["label_id"] == label_id), None)
    if label is None:
        return label_id
    return _get_message_by_lang(label["label_name"], "en-US") or label_id


def _get_attribute_name_en_by_id(specs: dict[str, Any], attribute_id: str) -> str:
    attribute = next(
        (e for e in specs.get("additionals", []) if e["additional_data_definition_id"] == attribute_id),
        None,
    )
    if attribute is None:
        return attribute_id
    return _get_message_by_lang(attribute["name"], "en-US") or attribute_id


def _get_choice_name_en_by_id(attribute: dict[str, Any], choice_id: str) -> str:
    choice = next((e for e in attribute.get("choices", []) if e["choice_id"] == choice_id), None)
    if choice is None:
        return choice_id
    return _get_message_by_lang(choice["name"], "en-US") or choice_id


def _append_name_lines(lines: list[str], *, indent: str, label: str, values: Sequence[str]) -> None:
    if len(values) == 0:
        return
    lines.append(f"{indent}{label}:")
    lines.extend([f"{indent}- {value}" for value in values])


def _get_changed_field_names_from_label(diff: ChangedLabel) -> list[str]:
    field_names = []
    if diff.color_changed:
        field_names.append("color")
    if diff.keybind_changed:
        field_names.append("keybind")
    if diff.label_name_ja_changed:
        field_names.append("label_name_ja")
    if diff.label_name_en_changed:
        field_names.append("label_name_en")
    if diff.label_name_vi_changed:
        field_names.append("label_name_vi")
    if diff.attributes_changed:
        field_names.append("attributes")
    if diff.attributes_order_changed:
        field_names.append("attributes_order")
    if diff.field_values_changed:
        field_names.append("field_values")
    if diff.metadata_changed:
        field_names.append("metadata")
    if diff.annotation_type_changed:
        field_names.append("annotation_type")
    return field_names


def _get_changed_field_names_from_choice(diff: ChangedChoice) -> list[str]:
    field_names = []
    if diff.name_ja_changed:
        field_names.append("name_ja")
    if diff.name_en_changed:
        field_names.append("name_en")
    if diff.name_vi_changed:
        field_names.append("name_vi")
    if diff.keybind_changed:
        field_names.append("keybind")
    return field_names


def _get_changed_field_names_from_attribute(diff: ChangedAttribute) -> list[str]:
    field_names = []
    if diff.read_only_changed:
        field_names.append("read_only")
    if diff.name_ja_changed:
        field_names.append("name_ja")
    if diff.name_en_changed:
        field_names.append("name_en")
    if diff.name_vi_changed:
        field_names.append("name_vi")
    if diff.keybind_changed:
        field_names.append("keybind")
    if diff.type_changed:
        field_names.append("type")
    if diff.default_changed:
        field_names.append("default")
    if diff.metadata_changed:
        field_names.append("metadata")
    if diff.choices_changed:
        field_names.append("choices")
    if diff.choices_order_changed:
        field_names.append("choices_order")
    return field_names


def compare_choice(left_choice: dict[str, Any], right_choice: dict[str, Any]) -> ChangedChoice | None:
    """選択肢差分を比較する。"""
    diff = ChangedChoice(
        choice_id=right_choice["choice_id"],
        name_ja_changed=_get_message_by_lang(left_choice["name"], "ja-JP") != _get_message_by_lang(right_choice["name"], "ja-JP"),
        name_en_changed=_get_message_by_lang(left_choice["name"], "en-US") != _get_message_by_lang(right_choice["name"], "en-US"),
        name_vi_changed=_get_message_by_lang(left_choice["name"], "vi-VN") != _get_message_by_lang(right_choice["name"], "vi-VN"),
        keybind_changed=left_choice.get("keybind", []) != right_choice.get("keybind", []),
    )
    if not diff.has_changes():
        return None
    return diff


def compare_attribute(left_attribute: dict[str, Any], right_attribute: dict[str, Any]) -> ChangedAttribute | None:
    """属性差分を比較する。"""
    left_choice_list = left_attribute.get("choices", [])
    right_choice_list = right_attribute.get("choices", [])
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
        read_only_changed=left_attribute.get("read_only") != right_attribute.get("read_only"),
        name_ja_changed=_get_message_by_lang(left_attribute["name"], "ja-JP") != _get_message_by_lang(right_attribute["name"], "ja-JP"),
        name_en_changed=_get_message_by_lang(left_attribute["name"], "en-US") != _get_message_by_lang(right_attribute["name"], "en-US"),
        name_vi_changed=_get_message_by_lang(left_attribute["name"], "vi-VN") != _get_message_by_lang(right_attribute["name"], "vi-VN"),
        keybind_changed=left_attribute.get("keybind", []) != right_attribute.get("keybind", []),
        type_changed=left_attribute.get("type") != right_attribute.get("type"),
        default_changed=left_attribute.get("default") != right_attribute.get("default"),
        metadata_changed=left_attribute.get("metadata", {}) != right_attribute.get("metadata", {}),
        choices_changed=(len(added_choice_ids) > 0 or len(removed_choice_ids) > 0 or choices_order_changed or len(changed_choices) > 0),
        choices_order_changed=choices_order_changed,
        added_choice_ids=added_choice_ids,
        removed_choice_ids=removed_choice_ids,
        changed_choices=changed_choices,
    )
    if not diff.has_changes():
        return None
    return diff


def compare_attributes(left_specs: dict[str, Any], right_specs: dict[str, Any]) -> AttributesDiff:
    """属性一覧の差分を比較する。"""
    left_attribute_list = left_specs.get("additionals", [])
    right_attribute_list = right_specs.get("additionals", [])
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
        attribute_order_changed=_is_order_changed(left_attribute_ids, right_attribute_ids),
        added_attribute_ids=_get_added_ids(left_attribute_ids, right_attribute_ids),
        removed_attribute_ids=_get_removed_ids(left_attribute_ids, right_attribute_ids),
        changed_attributes=changed_attributes,
    )


def compare_label(left_label: dict[str, Any], right_label: dict[str, Any]) -> ChangedLabel | None:
    """ラベル差分を比較する。"""
    left_attribute_ids = left_label.get("additional_data_definitions", [])
    right_attribute_ids = right_label.get("additional_data_definitions", [])
    added_attribute_ids = _get_added_ids(left_attribute_ids, right_attribute_ids)
    removed_attribute_ids = _get_removed_ids(left_attribute_ids, right_attribute_ids)
    attributes_order_changed = _is_order_changed(left_attribute_ids, right_attribute_ids)

    diff = ChangedLabel(
        label_id=right_label["label_id"],
        color_changed=left_label.get("color") != right_label.get("color"),
        keybind_changed=left_label.get("keybind", []) != right_label.get("keybind", []),
        label_name_ja_changed=_get_message_by_lang(left_label["label_name"], "ja-JP") != _get_message_by_lang(right_label["label_name"], "ja-JP"),
        label_name_en_changed=_get_message_by_lang(left_label["label_name"], "en-US") != _get_message_by_lang(right_label["label_name"], "en-US"),
        label_name_vi_changed=_get_message_by_lang(left_label["label_name"], "vi-VN") != _get_message_by_lang(right_label["label_name"], "vi-VN"),
        attributes_changed=len(added_attribute_ids) > 0 or len(removed_attribute_ids) > 0 or attributes_order_changed,
        attributes_order_changed=attributes_order_changed,
        added_attribute_ids=added_attribute_ids,
        removed_attribute_ids=removed_attribute_ids,
        field_values_changed=left_label.get("field_values", {}) != right_label.get("field_values", {}),
        metadata_changed=left_label.get("metadata", {}) != right_label.get("metadata", {}),
        annotation_type_changed=left_label.get("annotation_type") != right_label.get("annotation_type"),
    )
    if not diff.has_changes():
        return None
    return diff


def compare_labels(left_specs: dict[str, Any], right_specs: dict[str, Any]) -> LabelsDiff:
    """ラベル一覧の差分を比較する。"""
    left_label_list = left_specs.get("labels", [])
    right_label_list = right_specs.get("labels", [])
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


def create_annotation_specs_diff(
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    *,
    targets: Iterable[str] | None = None,
) -> AnnotationSpecsDiff:
    """アノテーション仕様の差分を生成する。"""
    target_set = set(targets) if targets is not None else {"labels", "attributes"}

    return AnnotationSpecsDiff(
        labels=compare_labels(left_specs, right_specs) if "labels" in target_set else None,
        attributes=compare_attributes(left_specs, right_specs) if "attributes" in target_set else None,
    )


def format_annotation_specs_diff_as_text(
    diff: AnnotationSpecsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool = False,
) -> str:
    """アノテーション仕様の差分をテキスト形式に変換する。"""
    if not diff.has_changes():
        return "差分はありません。"

    lines: list[str] = []
    if diff.labels is not None:
        lines.extend(_format_labels_diff_as_text(diff.labels, left_specs=left_specs, right_specs=right_specs, detail=detail))
    if diff.labels is not None and diff.attributes is not None:
        lines.append("")
    if diff.attributes is not None:
        lines.extend(_format_attributes_diff_as_text(diff.attributes, left_specs=left_specs, right_specs=right_specs, detail=detail))
    return "\n".join(lines)


def _format_labels_diff_as_text(
    labels_diff: LabelsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> list[str]:
    lines = ["[labels]"]
    if not labels_diff.has_changes():
        lines.append("差分はありません。")
        return lines

    if labels_diff.label_order_changed:
        lines.append("label_order_changed: true")
        if detail:
            left_ids = [e["label_id"] for e in left_specs.get("labels", [])]
            right_ids = [e["label_id"] for e in right_specs.get("labels", [])]
            lines.extend(
                [
                    f"left_label_ids: {', '.join(left_ids)}",
                    f"right_label_ids: {', '.join(right_ids)}",
                ]
            )

    _append_name_lines(
        lines,
        indent="",
        label="added_labels",
        values=[_get_label_name_en_by_id(right_specs, e) for e in labels_diff.added_label_ids],
    )
    _append_name_lines(
        lines,
        indent="",
        label="removed_labels",
        values=[_get_label_name_en_by_id(left_specs, e) for e in labels_diff.removed_label_ids],
    )

    if len(labels_diff.changed_labels) == 0:
        return lines

    left_label_dict = {e["label_id"]: e for e in left_specs.get("labels", [])}
    right_label_dict = {e["label_id"]: e for e in right_specs.get("labels", [])}
    lines.append("changed_labels:")
    for changed_label in labels_diff.changed_labels:
        lines.append(f"  - label_name_en: {_get_label_name_en_by_id(right_specs, changed_label.label_id)}")
        if detail:
            _append_label_detail_lines(lines, changed_label, left_label=left_label_dict[changed_label.label_id], right_label=right_label_dict[changed_label.label_id])
        else:
            changed_field_names = _get_changed_field_names_from_label(changed_label)
            if len(changed_field_names) > 0:
                lines.append(f"    changed: {', '.join(changed_field_names)}")
            _append_name_lines(
                lines,
                indent="    ",
                label="added_attributes",
                values=[_get_attribute_name_en_by_id(right_specs, e) for e in changed_label.added_attribute_ids],
            )
            _append_name_lines(
                lines,
                indent="    ",
                label="removed_attributes",
                values=[_get_attribute_name_en_by_id(left_specs, e) for e in changed_label.removed_attribute_ids],
            )
    return lines


def _append_label_detail_lines(
    lines: list[str],
    changed_label: ChangedLabel,
    *,
    left_label: dict[str, Any],
    right_label: dict[str, Any],
) -> None:
    _append_detail_line(
        lines,
        indent="    ",
        name="color",
        changed=changed_label.color_changed,
        left_value=left_label.get("color"),
        right_value=right_label.get("color"),
    )
    _append_detail_line(
        lines,
        indent="    ",
        name="keybind",
        changed=changed_label.keybind_changed,
        left_value=left_label.get("keybind", []),
        right_value=right_label.get("keybind", []),
    )
    for name, lang, changed in [
        ("label_name_ja", "ja-JP", changed_label.label_name_ja_changed),
        ("label_name_en", "en-US", changed_label.label_name_en_changed),
        ("label_name_vi", "vi-VN", changed_label.label_name_vi_changed),
    ]:
        _append_detail_line(
            lines,
            indent="    ",
            name=name,
            changed=changed,
            left_value=_get_message_by_lang(left_label["label_name"], lang),
            right_value=_get_message_by_lang(right_label["label_name"], lang),
        )
    _append_detail_line(
        lines,
        indent="    ",
        name="attribute_ids",
        changed=changed_label.attributes_order_changed,
        left_value=left_label.get("additional_data_definitions", []),
        right_value=right_label.get("additional_data_definitions", []),
    )
    _append_id_lines(lines, indent="    ", label="added_attribute_ids", values=changed_label.added_attribute_ids)
    _append_id_lines(lines, indent="    ", label="removed_attribute_ids", values=changed_label.removed_attribute_ids)
    _append_detail_line(
        lines,
        indent="    ",
        name="field_values",
        changed=changed_label.field_values_changed,
        left_value=left_label.get("field_values", {}),
        right_value=right_label.get("field_values", {}),
    )
    _append_detail_line(
        lines,
        indent="    ",
        name="metadata",
        changed=changed_label.metadata_changed,
        left_value=left_label.get("metadata", {}),
        right_value=right_label.get("metadata", {}),
    )
    _append_detail_line(
        lines,
        indent="    ",
        name="annotation_type",
        changed=changed_label.annotation_type_changed,
        left_value=left_label.get("annotation_type"),
        right_value=right_label.get("annotation_type"),
    )


def _format_attributes_diff_as_text(
    attributes_diff: AttributesDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> list[str]:
    lines = ["[attributes]"]
    if not attributes_diff.has_changes():
        lines.append("差分はありません。")
        return lines

    if attributes_diff.attribute_order_changed:
        lines.append("attribute_order_changed: true")
        if detail:
            left_ids = [e["additional_data_definition_id"] for e in left_specs.get("additionals", [])]
            right_ids = [e["additional_data_definition_id"] for e in right_specs.get("additionals", [])]
            lines.extend(
                [
                    f"left_attribute_ids: {', '.join(left_ids)}",
                    f"right_attribute_ids: {', '.join(right_ids)}",
                ]
            )

    _append_name_lines(
        lines,
        indent="",
        label="added_attributes",
        values=[_get_attribute_name_en_by_id(right_specs, e) for e in attributes_diff.added_attribute_ids],
    )
    _append_name_lines(
        lines,
        indent="",
        label="removed_attributes",
        values=[_get_attribute_name_en_by_id(left_specs, e) for e in attributes_diff.removed_attribute_ids],
    )

    if len(attributes_diff.changed_attributes) == 0:
        return lines

    left_attribute_dict = {e["additional_data_definition_id"]: e for e in left_specs.get("additionals", [])}
    right_attribute_dict = {e["additional_data_definition_id"]: e for e in right_specs.get("additionals", [])}
    lines.append("changed_attributes:")
    for changed_attribute in attributes_diff.changed_attributes:
        lines.append(f"  - attribute_name_en: {_get_attribute_name_en_by_id(right_specs, changed_attribute.attribute_id)}")
        if detail:
            _append_attribute_detail_lines(
                lines,
                changed_attribute,
                left_attribute=left_attribute_dict[changed_attribute.attribute_id],
                right_attribute=right_attribute_dict[changed_attribute.attribute_id],
            )
        else:
            changed_field_names = _get_changed_field_names_from_attribute(changed_attribute)
            if len(changed_field_names) > 0:
                lines.append(f"    changed: {', '.join(changed_field_names)}")
            _append_name_lines(
                lines,
                indent="    ",
                label="added_choices",
                values=[_get_choice_name_en_by_id(right_attribute_dict[changed_attribute.attribute_id], e) for e in changed_attribute.added_choice_ids],
            )
            _append_name_lines(
                lines,
                indent="    ",
                label="removed_choices",
                values=[_get_choice_name_en_by_id(left_attribute_dict[changed_attribute.attribute_id], e) for e in changed_attribute.removed_choice_ids],
            )
            if len(changed_attribute.changed_choices) > 0:
                lines.append("    changed_choices:")
                for changed_choice in changed_attribute.changed_choices:
                    lines.append(f"      - choice_name_en: {_get_choice_name_en_by_id(right_attribute_dict[changed_attribute.attribute_id], changed_choice.choice_id)}")
                    changed_choice_field_names = _get_changed_field_names_from_choice(changed_choice)
                    if len(changed_choice_field_names) > 0:
                        lines.append(f"        changed: {', '.join(changed_choice_field_names)}")
    return lines


def _append_attribute_detail_lines(
    lines: list[str],
    changed_attribute: ChangedAttribute,
    *,
    left_attribute: dict[str, Any],
    right_attribute: dict[str, Any],
) -> None:
    for name, changed, left_value, right_value in [
        (
            "read_only",
            changed_attribute.read_only_changed,
            left_attribute.get("read_only"),
            right_attribute.get("read_only"),
        ),
        (
            "keybind",
            changed_attribute.keybind_changed,
            left_attribute.get("keybind", []),
            right_attribute.get("keybind", []),
        ),
        (
            "type",
            changed_attribute.type_changed,
            left_attribute.get("type"),
            right_attribute.get("type"),
        ),
        (
            "default",
            changed_attribute.default_changed,
            left_attribute.get("default"),
            right_attribute.get("default"),
        ),
        (
            "metadata",
            changed_attribute.metadata_changed,
            left_attribute.get("metadata", {}),
            right_attribute.get("metadata", {}),
        ),
        (
            "choice_ids",
            changed_attribute.choices_order_changed,
            [e["choice_id"] for e in left_attribute.get("choices", [])],
            [e["choice_id"] for e in right_attribute.get("choices", [])],
        ),
    ]:
        _append_detail_line(
            lines,
            indent="    ",
            name=name,
            changed=changed,
            left_value=left_value,
            right_value=right_value,
        )
    for name, lang, changed in [
        ("name_ja", "ja-JP", changed_attribute.name_ja_changed),
        ("name_en", "en-US", changed_attribute.name_en_changed),
        ("name_vi", "vi-VN", changed_attribute.name_vi_changed),
    ]:
        _append_detail_line(
            lines,
            indent="    ",
            name=name,
            changed=changed,
            left_value=_get_message_by_lang(left_attribute["name"], lang),
            right_value=_get_message_by_lang(right_attribute["name"], lang),
        )
    _append_id_lines(lines, indent="    ", label="added_choice_ids", values=changed_attribute.added_choice_ids)
    _append_id_lines(lines, indent="    ", label="removed_choice_ids", values=changed_attribute.removed_choice_ids)
    if len(changed_attribute.changed_choices) == 0:
        return

    left_choice_dict = {e["choice_id"]: e for e in left_attribute.get("choices", [])}
    right_choice_dict = {e["choice_id"]: e for e in right_attribute.get("choices", [])}
    lines.append("    changed_choices:")
    for changed_choice in changed_attribute.changed_choices:
        lines.append(f"      - choice_id: {changed_choice.choice_id}")
        left_choice = left_choice_dict[changed_choice.choice_id]
        right_choice = right_choice_dict[changed_choice.choice_id]
        for name, lang, changed in [
            ("name_ja", "ja-JP", changed_choice.name_ja_changed),
            ("name_en", "en-US", changed_choice.name_en_changed),
            ("name_vi", "vi-VN", changed_choice.name_vi_changed),
        ]:
            _append_detail_line(
                lines,
                indent="        ",
                name=name,
                changed=changed,
                left_value=_get_message_by_lang(left_choice["name"], lang),
                right_value=_get_message_by_lang(right_choice["name"], lang),
            )
        _append_detail_line(
            lines,
            indent="        ",
            name="keybind",
            changed=changed_choice.keybind_changed,
            left_value=left_choice.get("keybind", []),
            right_value=right_choice.get("keybind", []),
        )
