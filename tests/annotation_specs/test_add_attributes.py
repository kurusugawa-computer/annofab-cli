from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from annofabcli.annotation_specs.add_attribute import AttributeType
from annofabcli.annotation_specs.add_attributes import (
    AttributeInput,
    build_request_body_for_add_attributes,
    read_attributes_json,
    resolve_attribute_inputs,
)

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
            '[{"attribute_type":"flag","attribute_name_en":"weather_checked","attribute_name_ja":"天気確認済み","attribute_id":"weather_checked_attr","label_name_ens":["car","bus"]},'
            '{"attribute_type":"text","attribute_name_en":"note2","label_ids":["car_label_id"]}]'
        )

        assert actual == [
            AttributeInput(
                attribute_type=AttributeType.FLAG,
                attribute_name_en="weather_checked",
                attribute_name_ja="天気確認済み",
                attribute_id="weather_checked_attr",
                label_name_ens=["car", "bus"],
            ),
            AttributeInput(
                attribute_type=AttributeType.TEXT,
                attribute_name_en="note2",
                label_ids=["car_label_id"],
            ),
        ]

    def test_attribute_input__invalid_attribute_type(self) -> None:
        with pytest.raises(ValidationError):
            AttributeInput(attribute_type=cast(Any, "select"), attribute_name_en="type2", label_name_ens=["car"])

    def test_read_attributes_json__attribute_name_en_required(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","label_name_ens":["car"]}]')

    def test_read_attributes_json__attribute_type_must_be_valid(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"select","attribute_name_en":"type2","label_name_ens":["car"]}]')

    def test_read_attributes_json__label_name_ens_and_label_ids_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_ens":["car"],"label_ids":["car_label_id"]}]')

    def test_read_attributes_json__label_name_ens_must_be_unique(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_ens":["car","car"]}]')


class TestResolveAttributeInputs:
    def test_resolve_attribute_inputs(self, annotation_specs: dict[str, Any]) -> None:
        actual = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AttributeType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_name_ja="天気確認済み",
                    attribute_id="weather_checked_attr",
                    label_name_ens=["car", "bus"],
                ),
                AttributeInput(
                    attribute_type=AttributeType.TEXT,
                    attribute_name_en="note2",
                    label_ids=["car_label_id"],
                ),
            ],
        )

        assert len(actual) == 2
        assert actual[0].new_attribute["additional_data_definition_id"] == "weather_checked_attr"
        assert actual[0].new_attribute["type"] == "flag"
        assert [label["label_id"] for label in actual[0].target_labels] == ["car_label_id", "22b5189b-af7b-4d9c-83a5-b92f122170ec"]
        assert actual[1].attribute_input.attribute_name_en == "note2"
        assert [label["label_id"] for label in actual[1].target_labels] == ["car_label_id"]

    def test_resolve_attribute_inputs__duplicated_attribute_id_with_existing_attribute(self, annotation_specs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_inputs(
                annotation_specs,
                attribute_inputs=[
                    AttributeInput(
                        attribute_type=AttributeType.FLAG,
                        attribute_name_en="weather_checked",
                        attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                        label_name_ens=["car"],
                    )
                ],
            )


class TestBuildRequestBodyForAddAttributes:
    def test_build_request_body_for_add_attributes(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AttributeType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_name_ja="天気確認済み",
                    attribute_id="weather_checked_attr",
                    label_name_ens=["car", "bus"],
                ),
                AttributeInput(
                    attribute_type=AttributeType.TEXT,
                    attribute_name_en="note2",
                    attribute_id="note2_attr",
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
        assert actual["additionals"][-1]["additional_data_definition_id"] == "note2_attr"

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        bus_label = next(label for label in actual["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        bike_label = next(label for label in actual["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")

        assert "weather_checked_attr" in car_label["additional_data_definitions"]
        assert "note2_attr" in car_label["additional_data_definitions"]
        assert "weather_checked_attr" in bus_label["additional_data_definitions"]
        assert "note2_attr" not in bus_label["additional_data_definitions"]
        assert "weather_checked_attr" not in bike_label["additional_data_definitions"]
        assert actual["comment"] == "以下の属性を追加しました。\n属性名(英語): weather_checked, note2"
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert all(additional["additional_data_definition_id"] != "weather_checked_attr" for additional in annotation_specs["additionals"])

    def test_build_request_body_for_add_attributes__custom_comment(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_attribute_inputs(
            annotation_specs,
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AttributeType.FLAG,
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
