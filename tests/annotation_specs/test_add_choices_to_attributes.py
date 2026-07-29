from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs.add_choice_attribute import ChoiceAttributeInput
from annofabcli.annotation_specs.add_choices_to_attributes import (
    AttributeChoicesInput,
    build_request_body_for_add_choices_to_attributes,
    read_attributes_json,
    resolve_attribute_choices_inputs,
    validate_attribute_choices_inputs,
)

DATA_DIR = Path("./tests/data/annotation_specs")
TYPE_ATTRIBUTE_ID = "71620647-98cf-48ad-b43b-4af425a24f32"
UNCLEAR_ATTRIBUTE_ID = "f12a0b59-dfce-4241-bb87-4b2c0259fc6f"


@pytest.fixture
def annotation_specs() -> dict:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestResolveAttributeChoicesInputs:
    def test_resolve_attribute_choices_inputs(self, annotation_specs: dict) -> None:
        annotation_specs["additionals"].append(
            {
                "additional_data_definition_id": "weather_attribute_id",
                "read_only": False,
                "name": {"messages": [{"lang": "en-US", "message": "weather"}], "default_lang": "en-US"},
                "keybind": [],
                "type": "choice",
                "default": "",
                "choices": [],
                "metadata": {},
            }
        )

        actual = resolve_attribute_choices_inputs(
            annotation_specs,
            attribute_choices_inputs=[
                AttributeChoicesInput(
                    attribute_id=TYPE_ATTRIBUTE_ID,
                    choices=[
                        ChoiceAttributeInput(choice_id="xlarge", choice_name_en="xlarge", choice_name_ja="特大", is_default=True),
                        ChoiceAttributeInput(choice_id="tiny", choice_name_en="tiny", choice_name_ja="極小"),
                    ],
                ),
                AttributeChoicesInput(
                    attribute_id="weather_attribute_id",
                    choices=[ChoiceAttributeInput(choice_id="rainy", choice_name_en="rainy", choice_name_ja="雨")],
                ),
            ],
        )

        assert [e.target_attribute["additional_data_definition_id"] for e in actual] == [TYPE_ATTRIBUTE_ID, "weather_attribute_id"]
        assert [choice["choice_id"] for choice in actual[0].added_choices] == ["xlarge", "tiny"]
        assert actual[0].target_attribute["default"] == ""

    def test_resolve_attribute_choices_inputs__attribute_not_choice(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_choices_inputs(
                annotation_specs,
                attribute_choices_inputs=[
                    AttributeChoicesInput(
                        attribute_id=UNCLEAR_ATTRIBUTE_ID,
                        choices=[ChoiceAttributeInput(choice_id="yes", choice_name_en="yes")],
                    )
                ],
            )


class TestValidateAttributeChoicesInputs:
    def test_validate_attribute_choices_inputs__empty(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_choices_inputs([])

    def test_validate_attribute_choices_inputs__duplicated_attribute_id(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_choices_inputs(
                [
                    AttributeChoicesInput(attribute_id=TYPE_ATTRIBUTE_ID, choices=[ChoiceAttributeInput(choice_id="xlarge", choice_name_en="xlarge")]),
                    AttributeChoicesInput(attribute_id=TYPE_ATTRIBUTE_ID, choices=[ChoiceAttributeInput(choice_id="tiny", choice_name_en="tiny")]),
                ]
            )


class TestBuildRequestBodyForAddChoicesToAttributes:
    def test_build_request_body_for_add_choices_to_attributes(self, annotation_specs: dict) -> None:
        annotation_specs["additionals"].append(
            {
                "additional_data_definition_id": "weather_attribute_id",
                "read_only": False,
                "name": {"messages": [{"lang": "en-US", "message": "weather"}], "default_lang": "en-US"},
                "keybind": [],
                "type": "choice",
                "default": "",
                "choices": [],
                "metadata": {},
            }
        )
        resolved_inputs = resolve_attribute_choices_inputs(
            annotation_specs,
            attribute_choices_inputs=[
                AttributeChoicesInput(
                    attribute_id=TYPE_ATTRIBUTE_ID,
                    choices=[ChoiceAttributeInput(choice_id="xlarge", choice_name_en="xlarge"), ChoiceAttributeInput(choice_id="tiny", choice_name_en="tiny")],
                ),
                AttributeChoicesInput(attribute_id="weather_attribute_id", choices=[ChoiceAttributeInput(choice_id="rainy", choice_name_en="rainy")]),
            ],
        )

        actual = build_request_body_for_add_choices_to_attributes(
            annotation_specs,
            resolved_added_choices_inputs=resolved_inputs,
            comment=None,
        )

        type_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID)
        assert [choice["choice_id"] for choice in type_attribute["choices"][-2:]] == ["xlarge", "tiny"]
        weather_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "weather_attribute_id")
        assert [choice["choice_id"] for choice in weather_attribute["choices"]] == ["rainy"]
        assert type_attribute["default"] == ""
        assert actual["comment"].startswith("以下の選択肢を属性に追加しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_add_choices_to_attributes__custom_comment(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_attribute_choices_inputs(
            annotation_specs,
            attribute_choices_inputs=[AttributeChoicesInput(attribute_id=TYPE_ATTRIBUTE_ID, choices=[ChoiceAttributeInput(choice_id="xlarge", choice_name_en="xlarge")])],
        )

        actual = build_request_body_for_add_choices_to_attributes(
            annotation_specs,
            resolved_added_choices_inputs=resolved_inputs,
            comment="custom",
        )

        assert actual["comment"] == "custom"


class TestReadAttributesJson:
    def test_read_attributes_json(self) -> None:
        actual = read_attributes_json(
            f'[{{"attribute_id":"{TYPE_ATTRIBUTE_ID}","choices":[{{"choice_id":"xlarge","choice_name_en":"xlarge","choice_name_ja":"特大","is_default":true}},{{"choice_id":"tiny","choice_name_en":"tiny"}}]}}]'
        )

        assert actual == [
            AttributeChoicesInput(
                attribute_id=TYPE_ATTRIBUTE_ID,
                choices=[
                    ChoiceAttributeInput(choice_id="xlarge", choice_name_en="xlarge", choice_name_ja="特大", is_default=True),
                    ChoiceAttributeInput(choice_id="tiny", choice_name_en="tiny"),
                ],
            )
        ]

    def test_read_attributes_json__attribute_must_be_object(self) -> None:
        with pytest.raises(TypeError):
            read_attributes_json('["invalid"]')

    def test_read_attributes_json__choices_must_be_list(self) -> None:
        with pytest.raises(TypeError):
            read_attributes_json(f'[{{"attribute_id":"{TYPE_ATTRIBUTE_ID}","choices":"invalid"}}]')

    def test_read_attributes_json__choice_must_be_object(self) -> None:
        with pytest.raises(TypeError):
            read_attributes_json(f'[{{"attribute_id":"{TYPE_ATTRIBUTE_ID}","choices":["invalid"]}}]')

    def test_read_attributes_json__attribute_id_required(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"choices":[{"choice_id":"xlarge","choice_name_en":"xlarge"}]}]')

    def test_read_attributes_json__unexpected_key(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json(f'[{{"attribute_id":"{TYPE_ATTRIBUTE_ID}","choices":[{{"choice_id":"xlarge","choice_name_en":"xlarge"}}],"delete":true}}]')
