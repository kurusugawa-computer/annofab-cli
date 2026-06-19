from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import pytest
from annofabapi.pydantic_models.additional_data_definition_type import AdditionalDataDefinitionType
from pydantic import ValidationError

from annofabcli.annotation_specs.add_attributes import (
    AttributeInput,
    build_request_body_for_add_attributes,
    read_attributes_json,
    resolve_attribute_inputs,
)
from annofabcli.annotation_specs.add_choice_attribute import ChoiceAttributeInput

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict[str, Any]:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        result = json.load(f)
    result["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return result


class TestReadAttributesJson:
    def test_read_attributes_json(self) -> None:
        actual = read_attributes_json(
            '[{"attribute_type":"flag","attribute_name_en":"weather_checked","attribute_name_ja":"天気確認済み","attribute_id":"weather_checked_attr","read_only":true,"label_name_ens":["car","bus"]},'
            '{"attribute_type":"select","attribute_name_en":"weather","choices":[{"choice_id":"sunny","choice_name_en":"sunny","choice_name_ja":"晴れ","is_default":true},{"choice_name_en":"cloudy"}],"label_ids":["car_label_id"]}]'
        )

        assert actual == [
            AttributeInput(
                attribute_type=AdditionalDataDefinitionType.FLAG,
                attribute_name_en="weather_checked",
                attribute_name_ja="天気確認済み",
                attribute_id="weather_checked_attr",
                read_only=True,
                label_name_ens=["car", "bus"],
            ),
            AttributeInput(
                attribute_type=AdditionalDataDefinitionType.SELECT,
                attribute_name_en="weather",
                label_ids=["car_label_id"],
                choices=[
                    ChoiceAttributeInput(
                        choice_id="sunny",
                        choice_name_en="sunny",
                        choice_name_ja="晴れ",
                        is_default=True,
                    ),
                    ChoiceAttributeInput(
                        choice_name_en="cloudy",
                    ),
                ],
            ),
        ]

    def test_attribute_input__invalid_attribute_type(self) -> None:
        with pytest.raises(ValidationError):
            AttributeInput(attribute_type=cast(Any, "unsupported"), attribute_name_en="type2", label_name_ens=["car"])

    def test_read_attributes_json__attribute_name_en_required(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","label_name_ens":["car"]}]')

    def test_read_attributes_json__attribute_type_must_be_valid(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"unsupported","attribute_name_en":"type2","label_name_ens":["car"]}]')

    def test_read_attributes_json__label_name_ens_and_label_ids_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_ens":["car"],"label_ids":["car_label_id"]}]')

    def test_read_attributes_json__label_name_ens_must_be_unique(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_ens":["car","car"]}]')

    def test_read_attributes_json__choice_attribute_requires_choices(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"select","attribute_name_en":"weather","label_name_ens":["car"]}]')

    def test_read_attributes_json__choice_attribute_must_have_two_or_more_choices(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"choice","attribute_name_en":"weather","choices":[{"choice_name_en":"sunny"}],"label_name_ens":["car"]}]')

    def test_read_attributes_json__non_choice_attribute_rejects_choices(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","choices":[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}],"label_name_ens":["car"]}]')


class TestResolveAttributeInputs:
    def test_resolve_attribute_inputs(self, annotation_specs: dict[str, Any]) -> None:
        actual = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_name_ja="天気確認済み",
                    attribute_id="weather_checked_attr",
                    read_only=True,
                    label_name_ens=["car", "bus"],
                ),
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.SELECT,
                    attribute_name_en="weather",
                    attribute_id="weather_attr",
                    choices=[
                        ChoiceAttributeInput(choice_name_en="sunny", is_default=True),
                        ChoiceAttributeInput(choice_name_en="cloudy"),
                    ],
                    label_ids=["car_label_id"],
                ),
            ],
        )

        assert len(actual) == 2
        assert actual[0].new_attribute["additional_data_definition_id"] == "weather_checked_attr"
        assert actual[0].new_attribute["type"] == "flag"
        assert actual[0].new_attribute["read_only"] is True
        assert [label["label_id"] for label in actual[0].target_labels] == ["car_label_id", "22b5189b-af7b-4d9c-83a5-b92f122170ec"]
        assert actual[1].attribute_input.attribute_name_en == "weather"
        assert actual[1].new_attribute["type"] == "select"
        assert len(actual[1].new_attribute["choices"]) == 2
        assert [label["label_id"] for label in actual[1].target_labels] == ["car_label_id"]

    def test_resolve_attribute_inputs__duplicated_attribute_id_with_existing_attribute(self, annotation_specs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_inputs(
                annotation_specs,
                attribute_inputs=[
                    AttributeInput(
                        attribute_type=AdditionalDataDefinitionType.FLAG,
                        attribute_name_en="weather_checked",
                        attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                        label_name_ens=["car"],
                    )
                ],
            )

    def test_resolve_attribute_inputs__duplicated_attribute_name_with_existing_attribute__warning(
        self,
        annotation_specs: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING)

        actual = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.CHOICE,
                    attribute_name_en="type",
                    attribute_id="weather_attr",
                    choices=[
                        ChoiceAttributeInput(choice_name_en="sunny"),
                        ChoiceAttributeInput(choice_name_en="cloudy"),
                    ],
                    label_name_ens=["car"],
                )
            ],
        )

        assert len(actual) == 1
        assert "属性名(英語)='type' の属性は既に存在しますが、処理を継続します。" in caplog.text


class TestBuildRequestBodyForAddAttributes:
    def test_build_request_body_for_add_attributes(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_name_ja="天気確認済み",
                    attribute_id="weather_checked_attr",
                    label_name_ens=["car", "bus"],
                ),
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.SELECT,
                    attribute_name_en="weather",
                    attribute_id="weather_attr",
                    read_only=True,
                    choices=[
                        ChoiceAttributeInput(choice_name_en="sunny", is_default=True),
                        ChoiceAttributeInput(choice_name_en="cloudy"),
                    ],
                    label_ids=["car_label_id"],
                ),
            ],
        )

        actual = build_request_body_for_add_attributes(
            annotation_specs,
            resolved_inputs=resolved_inputs,
            comment=None,
        )

        assert actual["additionals"][-2]["additional_data_definition_id"] == "weather_checked_attr"
        assert actual["additionals"][-1]["additional_data_definition_id"] == "weather_attr"
        assert actual["additionals"][-1]["type"] == "select"
        assert actual["additionals"][-1]["read_only"] is True
        assert len(actual["additionals"][-1]["choices"]) == 2

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        bus_label = next(label for label in actual["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        bike_label = next(label for label in actual["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")

        assert "weather_checked_attr" in car_label["additional_data_definitions"]
        assert "weather_attr" in car_label["additional_data_definitions"]
        assert "weather_checked_attr" in bus_label["additional_data_definitions"]
        assert "weather_attr" not in bus_label["additional_data_definitions"]
        assert "weather_checked_attr" not in bike_label["additional_data_definitions"]
        assert actual["comment"] == "以下の属性を追加しました。\n属性名(英語): weather_checked, weather"
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert all(additional["additional_data_definition_id"] != "weather_checked_attr" for additional in annotation_specs["additionals"])

    def test_build_request_body_for_add_attributes__custom_comment(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AdditionalDataDefinitionType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_id="weather_checked_attr",
                    label_name_ens=["car"],
                )
            ],
        )

        actual = build_request_body_for_add_attributes(
            annotation_specs,
            resolved_inputs=resolved_inputs,
            comment="custom comment",
        )

        assert actual["comment"] == "custom comment"
