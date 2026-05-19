from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from annofabapi.util.annotation_specs import STR_LANG, get_message_with_lang
from annofabapi.util.attribute_restrictions import Restriction

from annofabcli.annotation_specs.color import RgbColor, rgb_to_hex
from annofabcli.annotation_specs.diff_models import (
    AnnotationSpecsDiff,
    AttributeRestrictionDiffItem,
    AttributeRestrictionsDiff,
    AttributesDiff,
    ChangedAttribute,
    ChangedChoice,
    ChangedLabel,
    JsonValue,
    LabelsDiff,
)
from annofabcli.common.annofab.annotation_specs import keybind_to_text

INDENT = "  "
"""テキスト出力で使うインデント文字列。"""


def _to_json_text(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _indent(level: int) -> str:
    return INDENT * level


def _to_color_code(color: RgbColor) -> str:
    return rgb_to_hex(color)


def _format_detail_line(
    *,
    level: int,
    name: str,
    changed: bool,
    left_value: JsonValue,
    right_value: JsonValue,
) -> list[str]:
    if not changed:
        return []
    return [f"{_indent(level)}{name}: {_to_json_text(left_value)} -> {_to_json_text(right_value)}"]


def _format_keybind_detail_line(
    *,
    level: int,
    changed: bool,
    left_value: list[dict[str, Any]],
    right_value: list[dict[str, Any]],
) -> list[str]:
    return _format_detail_line(
        level=level,
        name="keybind",
        changed=changed,
        left_value=keybind_to_text(left_value),
        right_value=keybind_to_text(right_value),
    )


def _get_label_name_en_by_id(specs: dict[str, Any], label_id: str) -> str:
    label = next((e for e in specs["labels"] if e["label_id"] == label_id), None)
    if label is None:
        return label_id
    return get_message_with_lang(label["label_name"], "en-US") or label_id


def _get_attribute_name_en_by_id(specs: dict[str, Any], attribute_id: str) -> str:
    attribute = next(
        (e for e in specs["additionals"] if e["additional_data_definition_id"] == attribute_id),
        None,
    )
    if attribute is None:
        return attribute_id
    return get_message_with_lang(attribute["name"], "en-US") or attribute_id


def _get_choice_name_en_by_id(attribute: dict[str, Any], choice_id: str) -> str:
    choice = next((e for e in attribute["choices"] if e["choice_id"] == choice_id), None)
    if choice is None:
        return choice_id
    return get_message_with_lang(choice["name"], "en-US") or choice_id


def _format_added_removed_lines(*, level: int, prefix: str, label: str, values: Sequence[str]) -> list[str]:
    return [f"{_indent(level)}{prefix} {label}: {value}" for value in values]


def _get_label_name_en_list_by_ids(specs: dict[str, Any], label_ids: Sequence[str]) -> list[str]:
    return [_get_label_name_en_by_id(specs, e) for e in label_ids]


def _get_attribute_name_en_list_by_ids(specs: dict[str, Any], attribute_ids: Sequence[str]) -> list[str]:
    return [_get_attribute_name_en_by_id(specs, e) for e in attribute_ids]


def _get_choice_name_en_list_by_ids(attribute: dict[str, Any], choice_ids: Sequence[str]) -> list[str]:
    return [_get_choice_name_en_by_id(attribute, e) for e in choice_ids]


def _get_attribute_restriction_text(specs: dict[str, Any], *, attribute_id: str, condition: dict[str, Any]) -> str:
    return Restriction.from_dict(
        {
            "additional_data_definition_id": attribute_id,
            "condition": condition,
        }
    ).to_human_readable(specs)


def _get_attribute_name_en_by_id_from_specs(specs_list: Sequence[dict[str, Any]], attribute_id: str) -> str:
    for specs in specs_list:
        name = _get_attribute_name_en_by_id(specs, attribute_id)
        if name != attribute_id:
            return name
    return attribute_id


def _get_changed_field_names_from_label(diff: ChangedLabel) -> list[str]:
    field_names = []
    if diff.label_name_en_changed:
        field_names.append("label_name_en")
    if diff.label_name_ja_changed:
        field_names.append("label_name_ja")
    if diff.label_name_vi_changed:
        field_names.append("label_name_vi")
    if diff.annotation_type_changed:
        field_names.append("annotation_type")
    if diff.color_changed:
        field_names.append("color")
    if diff.keybind_changed:
        field_names.append("keybind")
    if diff.has_attribute_relation_changes():
        field_names.append("attributes")
    if diff.attributes_order_changed:
        field_names.append("attributes_order")
    if diff.field_values_changed:
        field_names.append("field_values")
    if diff.metadata_changed:
        field_names.append("metadata")
    return field_names


def _get_changed_field_names_from_choice(diff: ChangedChoice) -> list[str]:
    field_names = []
    if diff.name_en_changed:
        field_names.append("name_en")
    if diff.name_ja_changed:
        field_names.append("name_ja")
    if diff.name_vi_changed:
        field_names.append("name_vi")
    if diff.keybind_changed:
        field_names.append("keybind")
    return field_names


def _get_changed_field_names_from_attribute(diff: ChangedAttribute) -> list[str]:
    field_names = []
    if diff.name_en_changed:
        field_names.append("name_en")
    if diff.name_ja_changed:
        field_names.append("name_ja")
    if diff.name_vi_changed:
        field_names.append("name_vi")
    if diff.type_changed:
        field_names.append("type")
    if diff.keybind_changed:
        field_names.append("keybind")
    if diff.default_changed:
        field_names.append("default")
    if diff.read_only_changed:
        field_names.append("read_only")
    if diff.has_choice_changes():
        field_names.append("choices")
    if diff.choices_order_changed:
        field_names.append("choices_order")
    if diff.metadata_changed:
        field_names.append("metadata")
    return field_names


def format_annotation_specs_diff_as_text(
    diff: AnnotationSpecsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool = False,
) -> str:
    """アノテーション仕様の差分をテキスト形式に変換する。"""
    if not diff.has_changes():
        return ""

    sections: list[list[str]] = []
    if diff.labels is not None and diff.labels.has_changes():
        sections.append(_format_labels_diff_as_text(diff.labels, left_specs=left_specs, right_specs=right_specs, detail=detail))
    if diff.attributes is not None and diff.attributes.has_changes():
        sections.append(_format_attributes_diff_as_text(diff.attributes, left_specs=left_specs, right_specs=right_specs, detail=detail))
    if diff.attribute_restrictions is not None and diff.attribute_restrictions.has_changes():
        sections.append(
            _format_attribute_restrictions_diff_as_text(
                diff.attribute_restrictions,
                left_specs=left_specs,
                right_specs=right_specs,
                detail=detail,
            )
        )
    return "\n\n".join("\n".join(section) for section in sections)


def _format_labels_diff_as_text(
    labels_diff: LabelsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> list[str]:
    lines = ["[labels]"]

    if labels_diff.label_order_changed:
        lines.append("~ label_order")
        if detail:
            lines.extend(
                _format_detail_line(
                    level=1,
                    name="label_order",
                    changed=True,
                    left_value=_get_label_name_en_list_by_ids(
                        left_specs,
                        [e["label_id"] for e in left_specs["labels"]],
                    ),
                    right_value=_get_label_name_en_list_by_ids(
                        right_specs,
                        [e["label_id"] for e in right_specs["labels"]],
                    ),
                )
            )

    lines.extend(_format_added_removed_lines(level=0, prefix="+", label="label", values=_get_label_name_en_list_by_ids(right_specs, labels_diff.added_label_ids)))
    lines.extend(_format_added_removed_lines(level=0, prefix="-", label="label", values=_get_label_name_en_list_by_ids(left_specs, labels_diff.removed_label_ids)))

    if len(labels_diff.changed_labels) == 0:
        return lines

    left_label_dict = {e["label_id"]: e for e in left_specs["labels"]}
    right_label_dict = {e["label_id"]: e for e in right_specs["labels"]}
    for changed_label in labels_diff.changed_labels:
        lines.append(f"~ label: {_get_label_name_en_by_id(right_specs, changed_label.label_id)}")
        if detail:
            lines.extend(
                _format_label_detail_lines(
                    changed_label,
                    left_specs=left_specs,
                    right_specs=right_specs,
                    left_label=left_label_dict[changed_label.label_id],
                    right_label=right_label_dict[changed_label.label_id],
                )
            )
        else:
            changed_field_names = _get_changed_field_names_from_label(changed_label)
            if len(changed_field_names) > 0:
                lines.append(f"  changed: {', '.join(changed_field_names)}")
            lines.extend(
                _format_added_removed_lines(
                    level=1,
                    prefix="+",
                    label="attributes",
                    values=[_get_attribute_name_en_by_id(right_specs, e) for e in changed_label.added_attribute_ids],
                )
            )
            lines.extend(
                _format_added_removed_lines(
                    level=1,
                    prefix="-",
                    label="attributes",
                    values=[_get_attribute_name_en_by_id(left_specs, e) for e in changed_label.removed_attribute_ids],
                )
            )
    return lines


def _format_label_detail_lines(
    changed_label: ChangedLabel,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    left_label: dict[str, Any],
    right_label: dict[str, Any],
) -> list[str]:
    lines = []
    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("label_name_en", "en-US", changed_label.label_name_en_changed),
        ("label_name_ja", "ja-JP", changed_label.label_name_ja_changed),
        ("label_name_vi", "vi-VN", changed_label.label_name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        lines.extend(
            _format_detail_line(
                level=1,
                name=name,
                changed=changed,
                left_value=get_message_with_lang(left_label["label_name"], lang),
                right_value=get_message_with_lang(right_label["label_name"], lang),
            )
        )
    lines.extend(
        _format_detail_line(
            level=1,
            name="annotation_type",
            changed=changed_label.annotation_type_changed,
            left_value=left_label["annotation_type"],
            right_value=right_label["annotation_type"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="color",
            changed=changed_label.color_changed,
            left_value=_to_color_code(left_label["color"]),
            right_value=_to_color_code(right_label["color"]),
        )
    )
    lines.extend(
        _format_keybind_detail_line(
            level=1,
            changed=changed_label.keybind_changed,
            left_value=left_label["keybind"],
            right_value=right_label["keybind"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="attributes",
            changed=changed_label.has_attribute_relation_changes(),
            left_value=_get_attribute_name_en_list_by_ids(
                left_specs,
                left_label["additional_data_definitions"],
            ),
            right_value=_get_attribute_name_en_list_by_ids(
                right_specs,
                right_label["additional_data_definitions"],
            ),
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="attributes_order",
            changed=changed_label.attributes_order_changed,
            left_value=_get_attribute_name_en_list_by_ids(
                left_specs,
                left_label["additional_data_definitions"],
            ),
            right_value=_get_attribute_name_en_list_by_ids(
                right_specs,
                right_label["additional_data_definitions"],
            ),
        )
    )
    lines.extend(
        _format_added_removed_lines(
            level=1,
            prefix="+",
            label="attributes",
            values=_get_attribute_name_en_list_by_ids(right_specs, changed_label.added_attribute_ids),
        )
    )
    lines.extend(
        _format_added_removed_lines(
            level=1,
            prefix="-",
            label="attributes",
            values=_get_attribute_name_en_list_by_ids(left_specs, changed_label.removed_attribute_ids),
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="field_values",
            changed=changed_label.field_values_changed,
            left_value=left_label["field_values"],
            right_value=right_label["field_values"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="metadata",
            changed=changed_label.metadata_changed,
            left_value=left_label["metadata"],
            right_value=right_label["metadata"],
        )
    )
    return lines


def _format_attributes_diff_as_text(
    attributes_diff: AttributesDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> list[str]:
    lines = ["[attributes]"]

    lines.extend(
        _format_added_removed_lines(
            level=0,
            prefix="+",
            label="attribute",
            values=[_get_attribute_name_en_by_id(right_specs, e) for e in attributes_diff.added_attribute_ids],
        )
    )
    lines.extend(
        _format_added_removed_lines(
            level=0,
            prefix="-",
            label="attribute",
            values=[_get_attribute_name_en_by_id(left_specs, e) for e in attributes_diff.removed_attribute_ids],
        )
    )

    if len(attributes_diff.changed_attributes) == 0:
        return lines

    left_attribute_dict = {e["additional_data_definition_id"]: e for e in left_specs["additionals"]}
    right_attribute_dict = {e["additional_data_definition_id"]: e for e in right_specs["additionals"]}
    for changed_attribute in attributes_diff.changed_attributes:
        lines.append(f"~ attribute: {_get_attribute_name_en_by_id(right_specs, changed_attribute.attribute_id)}")
        if detail:
            lines.extend(
                _format_attribute_detail_lines(
                    changed_attribute,
                    left_attribute=left_attribute_dict[changed_attribute.attribute_id],
                    right_attribute=right_attribute_dict[changed_attribute.attribute_id],
                )
            )
        else:
            changed_field_names = _get_changed_field_names_from_attribute(changed_attribute)
            if len(changed_field_names) > 0:
                lines.append(f"  changed: {', '.join(changed_field_names)}")
            lines.extend(
                _format_added_removed_lines(
                    level=1,
                    prefix="+",
                    label="choices",
                    values=[_get_choice_name_en_by_id(right_attribute_dict[changed_attribute.attribute_id], e) for e in changed_attribute.added_choice_ids],
                )
            )
            lines.extend(
                _format_added_removed_lines(
                    level=1,
                    prefix="-",
                    label="choices",
                    values=[_get_choice_name_en_by_id(left_attribute_dict[changed_attribute.attribute_id], e) for e in changed_attribute.removed_choice_ids],
                )
            )
            for changed_choice in changed_attribute.changed_choices:
                lines.append(f"  ~ choice: {_get_choice_name_en_by_id(right_attribute_dict[changed_attribute.attribute_id], changed_choice.choice_id)}")
                changed_choice_field_names = _get_changed_field_names_from_choice(changed_choice)
                if len(changed_choice_field_names) > 0:
                    lines.append(f"    changed: {', '.join(changed_choice_field_names)}")
    return lines


def _format_attribute_detail_lines(
    changed_attribute: ChangedAttribute,
    *,
    left_attribute: dict[str, Any],
    right_attribute: dict[str, Any],
) -> list[str]:
    lines = []
    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("name_en", "en-US", changed_attribute.name_en_changed),
        ("name_ja", "ja-JP", changed_attribute.name_ja_changed),
        ("name_vi", "vi-VN", changed_attribute.name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        lines.extend(
            _format_detail_line(
                level=1,
                name=name,
                changed=changed,
                left_value=get_message_with_lang(left_attribute["name"], lang),
                right_value=get_message_with_lang(right_attribute["name"], lang),
            )
        )
    lines.extend(
        _format_detail_line(
            level=1,
            name="type",
            changed=changed_attribute.type_changed,
            left_value=left_attribute["type"],
            right_value=right_attribute["type"],
        )
    )
    lines.extend(
        _format_keybind_detail_line(
            level=1,
            changed=changed_attribute.keybind_changed,
            left_value=left_attribute["keybind"],
            right_value=right_attribute["keybind"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="default",
            changed=changed_attribute.default_changed,
            left_value=left_attribute["default"],
            right_value=right_attribute["default"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="read_only",
            changed=changed_attribute.read_only_changed,
            left_value=left_attribute["read_only"],
            right_value=right_attribute["read_only"],
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="choices",
            changed=changed_attribute.has_choice_changes(),
            left_value=_get_choice_name_en_list_by_ids(
                left_attribute,
                [e["choice_id"] for e in left_attribute["choices"]],
            ),
            right_value=_get_choice_name_en_list_by_ids(
                right_attribute,
                [e["choice_id"] for e in right_attribute["choices"]],
            ),
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="choices_order",
            changed=changed_attribute.choices_order_changed,
            left_value=_get_choice_name_en_list_by_ids(
                left_attribute,
                [e["choice_id"] for e in left_attribute["choices"]],
            ),
            right_value=_get_choice_name_en_list_by_ids(
                right_attribute,
                [e["choice_id"] for e in right_attribute["choices"]],
            ),
        )
    )
    lines.extend(
        _format_detail_line(
            level=1,
            name="metadata",
            changed=changed_attribute.metadata_changed,
            left_value=left_attribute["metadata"],
            right_value=right_attribute["metadata"],
        )
    )
    lines.extend(
        _format_added_removed_lines(
            level=1,
            prefix="+",
            label="choices",
            values=_get_choice_name_en_list_by_ids(right_attribute, changed_attribute.added_choice_ids),
        )
    )
    lines.extend(
        _format_added_removed_lines(
            level=1,
            prefix="-",
            label="choices",
            values=_get_choice_name_en_list_by_ids(left_attribute, changed_attribute.removed_choice_ids),
        )
    )
    if len(changed_attribute.changed_choices) == 0:
        return lines

    left_choice_dict = {e["choice_id"]: e for e in left_attribute["choices"]}
    right_choice_dict = {e["choice_id"]: e for e in right_attribute["choices"]}
    for changed_choice in changed_attribute.changed_choices:
        lines.append(f"  ~ choice: {_get_choice_name_en_by_id(right_attribute, changed_choice.choice_id)}")
        left_choice = left_choice_dict[changed_choice.choice_id]
        right_choice = right_choice_dict[changed_choice.choice_id]
        detail_targets = [
            ("name_en", "en-US", changed_choice.name_en_changed),
            ("name_ja", "ja-JP", changed_choice.name_ja_changed),
            ("name_vi", "vi-VN", changed_choice.name_vi_changed),
        ]
        for name, lang, changed in detail_targets:
            lines.extend(
                _format_detail_line(
                    level=2,
                    name=name,
                    changed=changed,
                    left_value=get_message_with_lang(left_choice["name"], lang),
                    right_value=get_message_with_lang(right_choice["name"], lang),
                )
            )
        lines.extend(
            _format_keybind_detail_line(
                level=2,
                changed=changed_choice.keybind_changed,
                left_value=left_choice["keybind"],
                right_value=right_choice["keybind"],
            )
        )
    return lines


def _format_attribute_restriction_lines(
    *,
    level: int,
    prefix: str,
    specs: dict[str, Any],
    attribute_id: str,
    restrictions: Sequence[AttributeRestrictionDiffItem],
    detail: bool,
) -> list[str]:
    if len(restrictions) == 0:
        return []

    lines = []
    for restriction in restrictions:
        restriction_text = _get_attribute_restriction_text(specs, attribute_id=attribute_id, condition=restriction.condition)
        lines.append(f"{_indent(level)}{prefix} restriction: {restriction_text}")
        if detail:
            lines.append(f"{_indent(level + 1)}condition: {_to_json_text(restriction.condition)}")
    return lines


def _format_attribute_restrictions_diff_as_text(
    attribute_restrictions_diff: AttributeRestrictionsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> list[str]:
    lines = ["[attribute_restrictions]"]

    for changed_attribute_restriction in attribute_restrictions_diff.changed_attribute_restrictions:
        attribute_id = changed_attribute_restriction.attribute_id
        lines.append(f"~ attribute: {_get_attribute_name_en_by_id_from_specs([right_specs, left_specs], attribute_id)}")
        lines.extend(
            _format_attribute_restriction_lines(
                level=1,
                prefix="+",
                specs=right_specs,
                attribute_id=attribute_id,
                restrictions=changed_attribute_restriction.added_restrictions,
                detail=detail,
            )
        )
        lines.extend(
            _format_attribute_restriction_lines(
                level=1,
                prefix="-",
                specs=left_specs,
                attribute_id=attribute_id,
                restrictions=changed_attribute_restriction.removed_restrictions,
                detail=detail,
            )
        )
    return lines
