from __future__ import annotations

import json
from pathlib import Path

import pytest
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

from annofabcli.annotation_specs.attribute_required import (
    REQUIRED_CONDITION,
    build_request_body_for_set_attribute_required,
    build_request_body_for_unset_attribute_required,
    create_required_restriction,
    is_required_restriction,
    resolve_target_attributes_to_set_required,
    resolve_target_attributes_to_unset_required,
)
from annofabcli.annotation_specs.utils import get_target_attributes

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestIsRequiredRestriction:
    def test_true(self) -> None:
        assert is_required_restriction(create_required_restriction("attr1")) is True

    def test_false_when_attribute_id_is_different(self) -> None:
        assert is_required_restriction(create_required_restriction("attr1"), attribute_id="attr2") is False

    def test_false_when_condition_is_different(self) -> None:
        restriction = {"additional_data_definition_id": "attr1", "condition": {"value": "foo", "_type": "NotEquals"}}
        assert is_required_restriction(restriction) is False


class TestGetTargetAttributes:
    def test_empty_input(self, annotation_specs: dict) -> None:
        annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

        with pytest.raises(ValueError):
            get_target_attributes(
                annotation_specs_accessor,
                attribute_ids=[],
                attribute_name_ens=None,
            )

    def test_attribute_name_en(self, annotation_specs: dict) -> None:
        annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

        actual = get_target_attributes(
            annotation_specs_accessor,
            attribute_ids=None,
            attribute_name_ens=["type", "link"],
        )

        assert [attribute["additional_data_definition_id"] for attribute in actual] == [
            "71620647-98cf-48ad-b43b-4af425a24f32",
            "15235360-4f46-42ac-927d-0e046bf52ddd",
        ]

    def test_duplicate_is_removed(self, annotation_specs: dict) -> None:
        annotation_specs_accessor = AnnotationSpecsAccessor(annotation_specs)

        actual = get_target_attributes(
            annotation_specs_accessor,
            attribute_ids=[
                "71620647-98cf-48ad-b43b-4af425a24f32",
                "71620647-98cf-48ad-b43b-4af425a24f32",
            ],
            attribute_name_ens=None,
        )

        assert len(actual) == 1


class TestSetAttributeRequired:
    def test_resolve_target_attributes_to_set_required(self, annotation_specs: dict) -> None:
        actual = resolve_target_attributes_to_set_required(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["type", "link"],
        )

        assert [(attribute.attribute_id, attribute.attribute_name_en) for attribute in actual] == [
            ("71620647-98cf-48ad-b43b-4af425a24f32", "type"),
            ("15235360-4f46-42ac-927d-0e046bf52ddd", "link"),
        ]

    def test_resolve_target_attributes_to_set_required__already_required_is_skipped(self, annotation_specs: dict) -> None:
        actual = resolve_target_attributes_to_set_required(
            annotation_specs,
            attribute_ids=["54fa5e97-6f88-49a4-aeb0-a91a15d11528", "15235360-4f46-42ac-927d-0e046bf52ddd"],
            attribute_name_ens=None,
        )

        assert [(attribute.attribute_id, attribute.attribute_name_en) for attribute in actual] == [("15235360-4f46-42ac-927d-0e046bf52ddd", "link")]

    def test_build_request_body_for_set_attribute_required(self, annotation_specs: dict) -> None:
        target_attributes_to_add = resolve_target_attributes_to_set_required(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["type", "link"],
        )

        actual = build_request_body_for_set_attribute_required(
            annotation_specs,
            target_attributes_to_add=target_attributes_to_add,
            comment=None,
        )

        added_restrictions = [restriction for restriction in actual["restrictions"] if restriction["condition"] == REQUIRED_CONDITION]
        added_attribute_ids = {restriction["additional_data_definition_id"] for restriction in added_restrictions}
        assert {"71620647-98cf-48ad-b43b-4af425a24f32", "15235360-4f46-42ac-927d-0e046bf52ddd"} <= added_attribute_ids
        assert actual["comment"] == "以下の属性を必須にしました。\ntype\nlink"

    def test_build_request_body_for_set_attribute_required__custom_comment(self, annotation_specs: dict) -> None:
        target_attributes_to_add = resolve_target_attributes_to_set_required(
            annotation_specs,
            attribute_ids=["15235360-4f46-42ac-927d-0e046bf52ddd"],
            attribute_name_ens=None,
        )

        actual = build_request_body_for_set_attribute_required(
            annotation_specs,
            target_attributes_to_add=target_attributes_to_add,
            comment="custom",
        )

        assert actual["comment"] == "custom"


class TestUnsetAttributeRequired:
    def test_resolve_target_attributes_to_unset_required(self, annotation_specs: dict) -> None:
        actual = resolve_target_attributes_to_unset_required(
            annotation_specs,
            attribute_ids=["54fa5e97-6f88-49a4-aeb0-a91a15d11528"],
            attribute_name_ens=None,
        )

        assert [(attribute.attribute_id, attribute.attribute_name_en) for attribute in actual] == [("54fa5e97-6f88-49a4-aeb0-a91a15d11528", "comment")]

    def test_resolve_target_attributes_to_unset_required__attribute_not_required(self, annotation_specs: dict) -> None:
        actual = resolve_target_attributes_to_unset_required(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["link"],
        )

        assert actual == []

    def test_build_request_body_for_unset_attribute_required(self, annotation_specs: dict) -> None:
        target_attributes_to_remove = resolve_target_attributes_to_unset_required(
            annotation_specs,
            attribute_ids=["54fa5e97-6f88-49a4-aeb0-a91a15d11528"],
            attribute_name_ens=None,
        )

        actual = build_request_body_for_unset_attribute_required(
            annotation_specs,
            target_attributes_to_remove=target_attributes_to_remove,
            comment=None,
        )

        remaining_required_restrictions = [
            restriction
            for restriction in actual["restrictions"]
            if restriction["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528" and restriction["condition"] == REQUIRED_CONDITION
        ]
        assert remaining_required_restrictions == []
        assert actual["comment"] == "以下の属性の必須制約を解除しました。\ncomment"
