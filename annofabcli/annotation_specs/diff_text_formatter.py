from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import yaml
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
    ChangedInspectionPhrase,
    ChangedLabel,
    InspectionPhrasesDiff,
    JsonValue,
    LabelsDiff,
    MetadataDiff,
    OptionDiff,
)
from annofabcli.common.annofab.annotation_specs import keybind_to_text


def _to_color_code(color: RgbColor) -> str:
    return rgb_to_hex(color)


def _dump_yaml(value: JsonValue) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()


def _to_display_text(value: JsonValue) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


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
    if diff.choice_name_en_changed:
        field_names.append("choice_name_en")
    if diff.choice_name_ja_changed:
        field_names.append("choice_name_ja")
    if diff.choice_name_vi_changed:
        field_names.append("choice_name_vi")
    if diff.keybind_changed:
        field_names.append("keybind")
    return field_names


def _get_changed_field_names_from_attribute(diff: ChangedAttribute) -> list[str]:
    field_names = []
    if diff.attribute_name_en_changed:
        field_names.append("attribute_name_en")
    if diff.attribute_name_ja_changed:
        field_names.append("attribute_name_ja")
    if diff.attribute_name_vi_changed:
        field_names.append("attribute_name_vi")
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


def _get_changed_field_names_from_inspection_phrase(diff: ChangedInspectionPhrase) -> list[str]:
    field_names = []
    if diff.inspection_phrase_name_en_changed:
        field_names.append("inspection_phrase_name_en")
    if diff.inspection_phrase_name_ja_changed:
        field_names.append("inspection_phrase_name_ja")
    if diff.inspection_phrase_name_vi_changed:
        field_names.append("inspection_phrase_name_vi")
    return field_names


def _append_if_not_empty(target: dict[str, JsonValue], key: str, value: JsonValue) -> None:
    if isinstance(value, list) and len(value) == 0:
        return
    if isinstance(value, dict) and len(value) == 0:
        return
    target[key] = value


def _put_detail_line(
    target: dict[str, JsonValue],
    *,
    name: str,
    changed: bool,
    left_value: JsonValue,
    right_value: JsonValue,
) -> None:
    if changed:
        target[name] = {"left": _to_display_text(left_value), "right": _to_display_text(right_value)}


def _put_keybind_detail_line(
    target: dict[str, JsonValue],
    *,
    changed: bool,
    left_value: list[dict[str, Any]],
    right_value: list[dict[str, Any]],
) -> None:
    _put_detail_line(
        target,
        name="keybind",
        changed=changed,
        left_value=keybind_to_text(left_value),
        right_value=keybind_to_text(right_value),
    )


def _append_detail_changes(item: dict[str, JsonValue], changes: dict[str, JsonValue]) -> None:
    _append_if_not_empty(item, "changes", changes)


def _create_label_text_item(changed_label: ChangedLabel, *, left_specs: dict[str, Any], right_specs: dict[str, Any]) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {
        "label_name_en": _get_label_name_en_by_id(right_specs, changed_label.label_id),
        "fields": _get_changed_field_names_from_label(changed_label),
    }
    _append_if_not_empty(item, "added_attributes", _get_attribute_name_en_list_by_ids(right_specs, changed_label.added_attribute_ids))
    _append_if_not_empty(item, "removed_attributes", _get_attribute_name_en_list_by_ids(left_specs, changed_label.removed_attribute_ids))
    return item


def _create_label_detail_item(
    changed_label: ChangedLabel,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    left_label: dict[str, Any],
    right_label: dict[str, Any],
) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {"label_name_en": _get_label_name_en_by_id(right_specs, changed_label.label_id)}
    changes: dict[str, JsonValue] = {}

    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("label_name_en", "en-US", changed_label.label_name_en_changed),
        ("label_name_ja", "ja-JP", changed_label.label_name_ja_changed),
        ("label_name_vi", "vi-VN", changed_label.label_name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        _put_detail_line(
            changes,
            name=name,
            changed=changed,
            left_value=get_message_with_lang(left_label["label_name"], lang),
            right_value=get_message_with_lang(right_label["label_name"], lang),
        )

    _put_detail_line(
        changes,
        name="annotation_type",
        changed=changed_label.annotation_type_changed,
        left_value=left_label["annotation_type"],
        right_value=right_label["annotation_type"],
    )
    _put_detail_line(
        changes,
        name="color",
        changed=changed_label.color_changed,
        left_value=_to_color_code(left_label["color"]),
        right_value=_to_color_code(right_label["color"]),
    )
    _put_keybind_detail_line(
        changes,
        changed=changed_label.keybind_changed,
        left_value=left_label["keybind"],
        right_value=right_label["keybind"],
    )
    _put_detail_line(
        changes,
        name="attributes",
        changed=changed_label.has_attribute_relation_changes(),
        left_value=_get_attribute_name_en_list_by_ids(left_specs, left_label["additional_data_definitions"]),
        right_value=_get_attribute_name_en_list_by_ids(right_specs, right_label["additional_data_definitions"]),
    )
    _put_detail_line(
        changes,
        name="attributes_order",
        changed=changed_label.attributes_order_changed,
        left_value=_get_attribute_name_en_list_by_ids(left_specs, left_label["additional_data_definitions"]),
        right_value=_get_attribute_name_en_list_by_ids(right_specs, right_label["additional_data_definitions"]),
    )
    _put_detail_line(
        changes,
        name="field_values",
        changed=changed_label.field_values_changed,
        left_value=left_label["field_values"],
        right_value=right_label["field_values"],
    )
    _put_detail_line(
        changes,
        name="metadata",
        changed=changed_label.metadata_changed,
        left_value=left_label["metadata"],
        right_value=right_label["metadata"],
    )
    _append_detail_changes(item, changes)
    _append_if_not_empty(item, "added_attributes", _get_attribute_name_en_list_by_ids(right_specs, changed_label.added_attribute_ids))
    _append_if_not_empty(item, "removed_attributes", _get_attribute_name_en_list_by_ids(left_specs, changed_label.removed_attribute_ids))
    return item


def _create_labels_section(
    labels_diff: LabelsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}

    if labels_diff.label_order_changed:
        section["label_order_changed"] = True

    _append_if_not_empty(section, "added", _get_label_name_en_list_by_ids(right_specs, labels_diff.added_label_ids))
    _append_if_not_empty(section, "removed", _get_label_name_en_list_by_ids(left_specs, labels_diff.removed_label_ids))

    if len(labels_diff.changed_labels) > 0:
        left_label_dict = {e["label_id"]: e for e in left_specs["labels"]}
        right_label_dict = {e["label_id"]: e for e in right_specs["labels"]}
        if detail:
            section["changed"] = [
                _create_label_detail_item(
                    changed_label,
                    left_specs=left_specs,
                    right_specs=right_specs,
                    left_label=left_label_dict[changed_label.label_id],
                    right_label=right_label_dict[changed_label.label_id],
                )
                for changed_label in labels_diff.changed_labels
            ]
        else:
            section["changed"] = [_create_label_text_item(changed_label, left_specs=left_specs, right_specs=right_specs) for changed_label in labels_diff.changed_labels]

    return section


def _create_choice_text_item(changed_choice: ChangedChoice, *, right_attribute: dict[str, Any]) -> dict[str, JsonValue]:
    return {
        "choice_name_en": _get_choice_name_en_by_id(right_attribute, changed_choice.choice_id),
        "fields": _get_changed_field_names_from_choice(changed_choice),
    }


def _create_choice_detail_item(
    changed_choice: ChangedChoice,
    *,
    left_choice: dict[str, Any],
    right_choice: dict[str, Any],
) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {
        "choice_name_en": get_message_with_lang(right_choice["name"], "en-US") or changed_choice.choice_id,
    }
    changes: dict[str, JsonValue] = {}
    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("choice_name_en", "en-US", changed_choice.choice_name_en_changed),
        ("choice_name_ja", "ja-JP", changed_choice.choice_name_ja_changed),
        ("choice_name_vi", "vi-VN", changed_choice.choice_name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        _put_detail_line(
            changes,
            name=name,
            changed=changed,
            left_value=get_message_with_lang(left_choice["name"], lang),
            right_value=get_message_with_lang(right_choice["name"], lang),
        )
    _put_keybind_detail_line(
        changes,
        changed=changed_choice.keybind_changed,
        left_value=left_choice["keybind"],
        right_value=right_choice["keybind"],
    )
    _append_detail_changes(item, changes)
    return item


def _create_attribute_text_item(
    changed_attribute: ChangedAttribute,
    *,
    left_attribute: dict[str, Any],
    right_attribute: dict[str, Any],
) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {
        "attribute_name_en": _get_attribute_name_en_by_id({"additionals": [right_attribute]}, changed_attribute.attribute_id),
        "fields": _get_changed_field_names_from_attribute(changed_attribute),
    }
    _append_if_not_empty(item, "added_choices", _get_choice_name_en_list_by_ids(right_attribute, changed_attribute.added_choice_ids))
    _append_if_not_empty(item, "removed_choices", _get_choice_name_en_list_by_ids(left_attribute, changed_attribute.removed_choice_ids))
    if len(changed_attribute.changed_choices) > 0:
        item["changed_choices"] = [_create_choice_text_item(changed_choice, right_attribute=right_attribute) for changed_choice in changed_attribute.changed_choices]
    return item


def _create_attribute_detail_item(
    changed_attribute: ChangedAttribute,
    *,
    left_attribute: dict[str, Any],
    right_attribute: dict[str, Any],
) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {
        "attribute_name_en": get_message_with_lang(right_attribute["name"], "en-US") or changed_attribute.attribute_id,
    }
    changes: dict[str, JsonValue] = {}

    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("attribute_name_en", "en-US", changed_attribute.attribute_name_en_changed),
        ("attribute_name_ja", "ja-JP", changed_attribute.attribute_name_ja_changed),
        ("attribute_name_vi", "vi-VN", changed_attribute.attribute_name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        _put_detail_line(
            changes,
            name=name,
            changed=changed,
            left_value=get_message_with_lang(left_attribute["name"], lang),
            right_value=get_message_with_lang(right_attribute["name"], lang),
        )

    _put_detail_line(
        changes,
        name="type",
        changed=changed_attribute.type_changed,
        left_value=left_attribute["type"],
        right_value=right_attribute["type"],
    )
    _put_keybind_detail_line(
        changes,
        changed=changed_attribute.keybind_changed,
        left_value=left_attribute["keybind"],
        right_value=right_attribute["keybind"],
    )
    _put_detail_line(
        changes,
        name="default",
        changed=changed_attribute.default_changed,
        left_value=left_attribute["default"],
        right_value=right_attribute["default"],
    )
    _put_detail_line(
        changes,
        name="read_only",
        changed=changed_attribute.read_only_changed,
        left_value=left_attribute["read_only"],
        right_value=right_attribute["read_only"],
    )
    _put_detail_line(
        changes,
        name="choices",
        changed=changed_attribute.has_choice_changes(),
        left_value=_get_choice_name_en_list_by_ids(left_attribute, [e["choice_id"] for e in left_attribute["choices"]]),
        right_value=_get_choice_name_en_list_by_ids(right_attribute, [e["choice_id"] for e in right_attribute["choices"]]),
    )
    _put_detail_line(
        changes,
        name="choices_order",
        changed=changed_attribute.choices_order_changed,
        left_value=_get_choice_name_en_list_by_ids(left_attribute, [e["choice_id"] for e in left_attribute["choices"]]),
        right_value=_get_choice_name_en_list_by_ids(right_attribute, [e["choice_id"] for e in right_attribute["choices"]]),
    )
    _put_detail_line(
        changes,
        name="metadata",
        changed=changed_attribute.metadata_changed,
        left_value=left_attribute["metadata"],
        right_value=right_attribute["metadata"],
    )
    _append_detail_changes(item, changes)
    _append_if_not_empty(item, "added_choices", _get_choice_name_en_list_by_ids(right_attribute, changed_attribute.added_choice_ids))
    _append_if_not_empty(item, "removed_choices", _get_choice_name_en_list_by_ids(left_attribute, changed_attribute.removed_choice_ids))

    if len(changed_attribute.changed_choices) > 0:
        left_choice_dict = {e["choice_id"]: e for e in left_attribute["choices"]}
        right_choice_dict = {e["choice_id"]: e for e in right_attribute["choices"]}
        item["changed_choices"] = [
            _create_choice_detail_item(
                changed_choice,
                left_choice=left_choice_dict[changed_choice.choice_id],
                right_choice=right_choice_dict[changed_choice.choice_id],
            )
            for changed_choice in changed_attribute.changed_choices
        ]
    return item


def _create_attributes_section(
    attributes_diff: AttributesDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}
    _append_if_not_empty(section, "added", [_get_attribute_name_en_by_id(right_specs, e) for e in attributes_diff.added_attribute_ids])
    _append_if_not_empty(section, "removed", [_get_attribute_name_en_by_id(left_specs, e) for e in attributes_diff.removed_attribute_ids])

    if len(attributes_diff.changed_attributes) > 0:
        left_attribute_dict = {e["additional_data_definition_id"]: e for e in left_specs["additionals"]}
        right_attribute_dict = {e["additional_data_definition_id"]: e for e in right_specs["additionals"]}
        if detail:
            section["changed"] = [
                _create_attribute_detail_item(
                    changed_attribute,
                    left_attribute=left_attribute_dict[changed_attribute.attribute_id],
                    right_attribute=right_attribute_dict[changed_attribute.attribute_id],
                )
                for changed_attribute in attributes_diff.changed_attributes
            ]
        else:
            section["changed"] = [
                _create_attribute_text_item(
                    changed_attribute,
                    left_attribute=left_attribute_dict[changed_attribute.attribute_id],
                    right_attribute=right_attribute_dict[changed_attribute.attribute_id],
                )
                for changed_attribute in attributes_diff.changed_attributes
            ]
    return section


def _create_restriction_text_item(
    *,
    specs: dict[str, Any],
    attribute_id: str,
    restrictions: Sequence[AttributeRestrictionDiffItem],
) -> list[str]:
    return [_get_attribute_restriction_text(specs, attribute_id=attribute_id, condition=restriction.condition) for restriction in restrictions]


def _create_attribute_restrictions_section(
    attribute_restrictions_diff: AttributeRestrictionsDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,  # noqa: ARG001
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}
    changed_items = []
    for changed_attribute_restriction in attribute_restrictions_diff.changed_attribute_restrictions:
        attribute_id = changed_attribute_restriction.attribute_id
        item_name = _get_attribute_name_en_by_id_from_specs([right_specs, left_specs], attribute_id)
        item: dict[str, JsonValue] = {"attribute_name_en": item_name}
        _append_if_not_empty(
            item,
            "added_restrictions",
            _create_restriction_text_item(
                specs=right_specs,
                attribute_id=attribute_id,
                restrictions=changed_attribute_restriction.added_restrictions,
            ),
        )
        _append_if_not_empty(
            item,
            "removed_restrictions",
            _create_restriction_text_item(
                specs=left_specs,
                attribute_id=attribute_id,
                restrictions=changed_attribute_restriction.removed_restrictions,
            ),
        )
        changed_items.append(item)
    _append_if_not_empty(section, "changed", changed_items)
    return section


def _create_inspection_phrase_text_item(changed_inspection_phrase: ChangedInspectionPhrase) -> dict[str, JsonValue]:
    return {
        "inspection_phrase_id": changed_inspection_phrase.inspection_phrase_id,
        "fields": _get_changed_field_names_from_inspection_phrase(changed_inspection_phrase),
    }


def _create_inspection_phrase_detail_item(
    changed_inspection_phrase: ChangedInspectionPhrase,
    *,
    left_inspection_phrase: dict[str, Any],
    right_inspection_phrase: dict[str, Any],
) -> dict[str, JsonValue]:
    item: dict[str, JsonValue] = {"inspection_phrase_id": changed_inspection_phrase.inspection_phrase_id}
    changes: dict[str, JsonValue] = {}
    detail_targets: list[tuple[str, STR_LANG, bool]] = [
        ("inspection_phrase_name_en", "en-US", changed_inspection_phrase.inspection_phrase_name_en_changed),
        ("inspection_phrase_name_ja", "ja-JP", changed_inspection_phrase.inspection_phrase_name_ja_changed),
        ("inspection_phrase_name_vi", "vi-VN", changed_inspection_phrase.inspection_phrase_name_vi_changed),
    ]
    for name, lang, changed in detail_targets:
        _put_detail_line(
            changes,
            name=name,
            changed=changed,
            left_value=get_message_with_lang(left_inspection_phrase["text"], lang),
            right_value=get_message_with_lang(right_inspection_phrase["text"], lang),
        )
    _append_detail_changes(item, changes)
    return item


def _create_inspection_phrases_section(
    inspection_phrases_diff: InspectionPhrasesDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}
    _append_if_not_empty(section, "added", inspection_phrases_diff.added_inspection_phrase_ids)
    _append_if_not_empty(section, "removed", inspection_phrases_diff.removed_inspection_phrase_ids)
    if len(inspection_phrases_diff.changed_inspection_phrases) > 0:
        if detail:
            left_inspection_phrase_dict = {e["id"]: e for e in left_specs["inspection_phrases"]}
            right_inspection_phrase_dict = {e["id"]: e for e in right_specs["inspection_phrases"]}
            section["changed"] = [
                _create_inspection_phrase_detail_item(
                    changed_inspection_phrase,
                    left_inspection_phrase=left_inspection_phrase_dict[changed_inspection_phrase.inspection_phrase_id],
                    right_inspection_phrase=right_inspection_phrase_dict[changed_inspection_phrase.inspection_phrase_id],
                )
                for changed_inspection_phrase in inspection_phrases_diff.changed_inspection_phrases
            ]
        else:
            section["changed"] = [_create_inspection_phrase_text_item(changed_inspection_phrase) for changed_inspection_phrase in inspection_phrases_diff.changed_inspection_phrases]
    return section


def _create_metadata_changed_detail_item(
    key: str,
    *,
    left_metadata: dict[str, Any],
    right_metadata: dict[str, Any],
) -> dict[str, JsonValue]:
    return {
        "key": key,
        "left": _to_display_text(left_metadata[key]),
        "right": _to_display_text(right_metadata[key]),
    }


def _create_metadata_section(
    metadata_diff: MetadataDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}
    left_metadata = left_specs["metadata"]
    right_metadata = right_specs["metadata"]
    _append_if_not_empty(section, "added", metadata_diff.added_metadata_keys)
    _append_if_not_empty(section, "removed", metadata_diff.removed_metadata_keys)
    if detail:
        _append_if_not_empty(
            section,
            "changed",
            [_create_metadata_changed_detail_item(key, left_metadata=left_metadata, right_metadata=right_metadata) for key in metadata_diff.changed_metadata_keys],
        )
        return section

    _append_if_not_empty(section, "changed", metadata_diff.changed_metadata_keys)
    return section


def _create_option_changed_detail_item(
    key: str,
    *,
    left_option: dict[str, Any],
    right_option: dict[str, Any],
) -> dict[str, JsonValue]:
    return {
        "key": key,
        "left": _to_display_text(left_option[key]),
        "right": _to_display_text(right_option[key]),
    }


def _create_option_section(
    option_diff: OptionDiff,
    *,
    left_specs: dict[str, Any],
    right_specs: dict[str, Any],
    detail: bool,
) -> dict[str, JsonValue]:
    section: dict[str, JsonValue] = {}
    left_option = left_specs.get("option", {})
    right_option = right_specs.get("option", {})
    _append_if_not_empty(section, "added", option_diff.added_option_keys)
    _append_if_not_empty(section, "removed", option_diff.removed_option_keys)
    if detail:
        _append_if_not_empty(
            section,
            "changed",
            [_create_option_changed_detail_item(key, left_option=left_option, right_option=right_option) for key in option_diff.changed_option_keys],
        )
        return section

    _append_if_not_empty(section, "changed", option_diff.changed_option_keys)
    return section


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

    sections: list[str] = []
    if diff.labels is not None and diff.labels.has_changes():
        labels_section = _create_labels_section(diff.labels, left_specs=left_specs, right_specs=right_specs, detail=detail)
        sections.append(f"[labels]\n{_dump_yaml(labels_section)}")
    if diff.attributes is not None and diff.attributes.has_changes():
        attributes_section = _create_attributes_section(diff.attributes, left_specs=left_specs, right_specs=right_specs, detail=detail)
        sections.append(f"[attributes]\n{_dump_yaml(attributes_section)}")
    if diff.attribute_restrictions is not None and diff.attribute_restrictions.has_changes():
        attribute_restrictions_section = _create_attribute_restrictions_section(
            diff.attribute_restrictions,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=detail,
        )
        sections.append(f"[attribute_restrictions]\n{_dump_yaml(attribute_restrictions_section)}")
    if diff.inspection_phrases is not None and diff.inspection_phrases.has_changes():
        inspection_phrases_section = _create_inspection_phrases_section(
            diff.inspection_phrases,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=detail,
        )
        sections.append(f"[inspection_phrases]\n{_dump_yaml(inspection_phrases_section)}")
    if diff.metadata is not None and diff.metadata.has_changes():
        metadata_section = _create_metadata_section(
            diff.metadata,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=detail,
        )
        sections.append(f"[metadata]\n{_dump_yaml(metadata_section)}")
    if diff.option is not None and diff.option.has_changes():
        option_section = _create_option_section(
            diff.option,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=detail,
        )
        sections.append(f"[option]\n{_dump_yaml(option_section)}")
    return "\n\n".join(sections)
