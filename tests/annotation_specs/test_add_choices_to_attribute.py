from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs.add_choice_attribute import read_choices_json
from annofabcli.annotation_specs.add_choices_to_attribute import (
    build_request_body_for_add_choices_to_attribute,
    read_choices_csv,
    resolve_added_choices_input,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestResolveAddedChoicesInput:
    def test_resolve_added_choices_input__attribute_id(self, annotation_specs: dict) -> None:
        actual = resolve_added_choices_input(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge","choice_name_ja":"特大"},{"choice_id":"tiny","choice_name_en":"tiny","choice_name_ja":"極小"}]'),
        )

        assert actual.target_attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"
        assert [choice["choice_id"] for choice in actual.added_choices] == ["xlarge", "tiny"]

    def test_resolve_added_choices_input__attribute_name_and_ignore_default(self, annotation_specs: dict) -> None:
        actual = resolve_added_choices_input(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge","is_default":true}]'),
        )

        assert actual.target_attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"
        assert actual.added_choices[0]["choice_id"] == "xlarge"

    def test_resolve_added_choices_input__ignore_default_in_csv(self, annotation_specs: dict, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text("choice_id,choice_name_en,is_default\nxlarge,xlarge,true\n", encoding="utf-8")

        actual = resolve_added_choices_input(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_inputs=read_choices_csv(csv_path),
        )

        assert actual.added_choices[0]["choice_id"] == "xlarge"

    def test_resolve_added_choices_input__duplicated_existing_choice_id(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_added_choices_input(
                annotation_specs,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_inputs=read_choices_json('[{"choice_id":"08ec927c-18e6-4bba-837a-b16de7061580","choice_name_en":"xlarge"}]'),
            )

    def test_resolve_added_choices_input__duplicated_existing_choice_name_en(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_added_choices_input(
                annotation_specs,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"large"}]'),
            )

    def test_resolve_added_choices_input__attribute_not_choice(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_added_choices_input(
                annotation_specs,
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge"}]'),
            )


class TestBuildRequestBodyForAddChoicesToAttribute:
    def test_build_request_body_for_add_choices_to_attribute(self, annotation_specs: dict) -> None:
        resolved_input = resolve_added_choices_input(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge","choice_name_ja":"特大"},{"choice_id":"tiny","choice_name_en":"tiny","choice_name_ja":"極小"}]'),
        )

        actual = build_request_body_for_add_choices_to_attribute(
            annotation_specs,
            resolved_added_choices_input=resolved_input,
            comment=None,
        )

        updated_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert [choice["choice_id"] for choice in updated_attribute["choices"][-2:]] == ["xlarge", "tiny"]
        assert updated_attribute["default"] == ""
        assert actual["comment"].startswith("以下の選択肢を属性に追加しました。")

    def test_build_request_body_for_add_choices_to_attribute__custom_comment(self, annotation_specs: dict) -> None:
        resolved_input = resolve_added_choices_input(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge","is_default":true}]'),
        )

        actual = build_request_body_for_add_choices_to_attribute(
            annotation_specs,
            resolved_added_choices_input=resolved_input,
            comment="custom",
        )

        updated_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert updated_attribute["default"] == ""
        assert actual["comment"] == "custom"

    def test_build_request_body_for_add_choices_to_attribute__ignore_default_when_default_already_exists(self, annotation_specs: dict) -> None:
        target_attribute = next(attribute for attribute in annotation_specs["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        target_attribute["default"] = "08ec927c-18e6-4bba-837a-b16de7061580"
        resolved_input = resolve_added_choices_input(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_inputs=read_choices_json('[{"choice_id":"xlarge","choice_name_en":"xlarge","is_default":true}]'),
        )

        actual = build_request_body_for_add_choices_to_attribute(
            annotation_specs,
            resolved_added_choices_input=resolved_input,
            comment=None,
        )

        updated_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert updated_attribute["default"] == "08ec927c-18e6-4bba-837a-b16de7061580"
