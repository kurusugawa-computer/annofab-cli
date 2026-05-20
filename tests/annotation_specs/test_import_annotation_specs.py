from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.import_annotation_specs import (
    ProtectedImportChanges,
    build_request_body_for_import_annotation_specs,
    create_protected_import_changes,
    validate_import_annotation_specs,
)


def _create_message(ja: str, en: str) -> dict[str, Any]:
    return {
        "messages": [
            {"lang": "ja-JP", "message": ja},
            {"lang": "en-US", "message": en},
        ],
        "default_lang": "ja-JP",
    }


def _create_choice(choice_id: str, *, ja: str, en: str) -> dict[str, Any]:
    return {
        "choice_id": choice_id,
        "name": _create_message(ja, en),
        "keybind": [],
    }


def _create_attribute(attribute_id: str, *, attribute_type: str, choices: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "additional_data_definition_id": attribute_id,
        "read_only": False,
        "name": _create_message(attribute_id, attribute_id),
        "keybind": [],
        "type": attribute_type,
        "default": choices[0]["choice_id"] if choices else False,
        "choices": choices if choices is not None else [],
        "metadata": {},
        "option": {},
    }


def _create_label(label_id: str, *, annotation_type: str = "bounding_box", attribute_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "label_id": label_id,
        "label_name": _create_message(label_id, label_id),
        "keybind": [],
        "annotation_type": annotation_type,
        "additional_data_definitions": attribute_ids if attribute_ids is not None else [],
        "color": {"red": 255, "green": 0, "blue": 0},
        "field_values": {},
        "metadata": {},
    }


def _create_annotation_specs() -> dict[str, Any]:
    return {
        "format_version": 3,
        "project_id": "src_prj",
        "labels": [
            _create_label("label_car", attribute_ids=["attr_occluded", "attr_truncated"]),
            _create_label("label_bus", attribute_ids=["attr_occluded"]),
        ],
        "additionals": [
            _create_attribute(
                "attr_occluded",
                attribute_type="select",
                choices=[
                    _create_choice("choice_yes", ja="はい", en="yes"),
                    _create_choice("choice_no", ja="いいえ", en="no"),
                ],
            ),
            _create_attribute("attr_truncated", attribute_type="flag"),
        ],
        "restrictions": [],
        "inspection_phrases": [],
        "metadata": {},
        "updated_datetime": "2026-04-24T00:00:00+09:00",
    }


def _assert_import_allowed(
    current_specs: dict[str, Any],
    imported_specs: dict[str, Any],
    *,
    used_label_ids: set[str] | None = None,
    used_label_attribute_pairs: set[tuple[str, str]] | None = None,
    used_choices: set[tuple[str, str, str]] | None = None,
) -> None:
    protected_changes = _create_protected_changes(
        current_specs,
        imported_specs,
        used_label_ids=used_label_ids,
        used_label_attribute_pairs=used_label_attribute_pairs,
        used_choices=used_choices,
    )
    validate_import_annotation_specs(protected_changes)


def _assert_import_blocked(
    current_specs: dict[str, Any],
    imported_specs: dict[str, Any],
    *,
    used_label_ids: set[str] | None = None,
    used_label_attribute_pairs: set[tuple[str, str]] | None = None,
    used_choices: set[tuple[str, str, str]] | None = None,
) -> None:
    protected_changes = _create_protected_changes(
        current_specs,
        imported_specs,
        used_label_ids=used_label_ids,
        used_label_attribute_pairs=used_label_attribute_pairs,
        used_choices=used_choices,
    )
    with pytest.raises(ValueError):
        validate_import_annotation_specs(protected_changes)


def _create_protected_changes(
    current_specs: dict[str, Any],
    imported_specs: dict[str, Any],
    *,
    used_label_ids: set[str] | None = None,
    used_label_attribute_pairs: set[tuple[str, str]] | None = None,
    used_choices: set[tuple[str, str, str]] | None = None,
) -> ProtectedImportChanges:
    used_label_ids = used_label_ids if used_label_ids is not None else set()
    used_label_attribute_pairs = used_label_attribute_pairs if used_label_attribute_pairs is not None else set()
    used_choices = used_choices if used_choices is not None else set()
    diff = create_annotation_specs_diff(current_specs, imported_specs, targets={"labels", "attributes"})
    return create_protected_import_changes(
        diff,
        current_specs,
        is_label_used=_to_used_checker(used_label_ids),
        is_attribute_used=lambda label_id, attribute_id: (label_id, attribute_id) in used_label_attribute_pairs,
        is_choice_used=lambda label_id, attribute_id, choice_id: (label_id, attribute_id, choice_id) in used_choices,
    )


def _to_used_checker(used_values: set[str]) -> Callable[[str], bool]:
    return lambda value: value in used_values


class TestBuildRequestBodyForImportAnnotationSpecs:
    def test_request_bodyを生成できる(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["project_id"] = "other_prj"
        imported_specs["updated_datetime"] = "2026-05-01T00:00:00+09:00"
        imported_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}

        actual = build_request_body_for_import_annotation_specs(current_specs, imported_specs, comment="importしました")

        assert actual["labels"][0]["color"] == {"red": 0, "green": 255, "blue": 0}
        assert actual["comment"] == "importしました"
        assert actual["last_updated_datetime"] == current_specs["updated_datetime"]
        assert "project_id" not in actual

    def test_comment未指定ならデフォルトコメントを設定する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)

        actual = build_request_body_for_import_annotation_specs(current_specs, imported_specs, comment=None)

        assert "annotation_specs import" in actual["comment"]


class TestValidateImportAnnotationSpecs:
    def test_中止対象差分がなければ許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}

        _assert_import_allowed(current_specs, imported_specs)

    def test_使われているラベルを削除する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"] = [label for label in imported_specs["labels"] if label["label_id"] != "label_car"]

        _assert_import_blocked(current_specs, imported_specs, used_label_ids={"label_car"})

    def test_使われていないラベルを削除する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"] = [label for label in imported_specs["labels"] if label["label_id"] != "label_car"]

        _assert_import_allowed(current_specs, imported_specs)

    def test_使われているラベルの種類を変更する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["annotation_type"] = "polygon"

        _assert_import_blocked(current_specs, imported_specs, used_label_ids={"label_car"})

    def test_使われていないラベルの種類を変更する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["annotation_type"] = "polygon"

        _assert_import_allowed(current_specs, imported_specs)

    def test_属性定義の削除だけでは中止しない(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"] = [attribute for attribute in imported_specs["additionals"] if attribute["additional_data_definition_id"] != "attr_truncated"]

        _assert_import_allowed(current_specs, imported_specs, used_label_attribute_pairs={("label_car", "attr_truncated")})

    def test_属性定義とラベルに含まれる属性を削除する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"] = [attribute for attribute in imported_specs["additionals"] if attribute["additional_data_definition_id"] != "attr_truncated"]
        imported_specs["labels"][0]["additional_data_definitions"] = ["attr_occluded"]

        _assert_import_blocked(current_specs, imported_specs, used_label_attribute_pairs={("label_car", "attr_truncated")})

    def test_使われていない属性定義とラベルに含まれる属性を削除する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"] = [attribute for attribute in imported_specs["additionals"] if attribute["additional_data_definition_id"] != "attr_truncated"]
        imported_specs["labels"][0]["additional_data_definitions"] = ["attr_occluded"]

        _assert_import_allowed(current_specs, imported_specs)

    def test_使われている属性の種類を変更する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"][1]["type"] = "integer"

        _assert_import_blocked(current_specs, imported_specs, used_label_attribute_pairs={("label_car", "attr_truncated")})

    def test_使われていない属性の種類を変更する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"][1]["type"] = "integer"

        _assert_import_allowed(current_specs, imported_specs)

    def test_使われている属性をラベルから削除する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["additional_data_definitions"] = ["attr_occluded"]

        _assert_import_blocked(current_specs, imported_specs, used_label_attribute_pairs={("label_car", "attr_truncated")})

    def test_使われていない属性をラベルから削除する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["additional_data_definitions"] = ["attr_occluded"]

        _assert_import_allowed(current_specs, imported_specs)

    def test_別ラベルで使われている属性をラベルから削除する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["labels"][0]["additional_data_definitions"] = ["attr_truncated"]

        _assert_import_allowed(current_specs, imported_specs, used_label_attribute_pairs={("label_bus", "attr_occluded")})

    def test_使われている選択肢を削除する場合は中止する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"][0]["choices"] = [choice for choice in imported_specs["additionals"][0]["choices"] if choice["choice_id"] != "choice_yes"]

        _assert_import_blocked(current_specs, imported_specs, used_choices={("label_car", "attr_occluded", "choice_yes")})

    def test_使われていない選択肢を削除する場合は許可する(self) -> None:
        current_specs = _create_annotation_specs()
        imported_specs = copy.deepcopy(current_specs)
        imported_specs["additionals"][0]["choices"] = [choice for choice in imported_specs["additionals"][0]["choices"] if choice["choice_id"] != "choice_yes"]

        _assert_import_allowed(current_specs, imported_specs)
