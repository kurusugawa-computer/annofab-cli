from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from annofabcli.annotation_specs.add_attribute import AttributeType
from annofabcli.annotation_specs.add_attributes import AddAttributesMain, AttributeInput, read_attributes_json

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class DummyApi:
    def __init__(self, annotation_specs: dict) -> None:
        self.annotation_specs = copy.deepcopy(annotation_specs)
        self.last_put: dict | None = None

    def get_annotation_specs(self, project_id: str, query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert query_params == {"v": "3"}
        return copy.deepcopy(self.annotation_specs), None

    def put_annotation_specs(self, project_id: str, query_params: dict, request_body: dict) -> None:
        assert project_id == "prj1"
        assert query_params == {"v": "3"}
        self.last_put = request_body


class DummyService:
    def __init__(self, annotation_specs: dict) -> None:
        self.api = DummyApi(annotation_specs)


class AddAttributesMainWithoutConfirm(AddAttributesMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


class TestAddAttributesMain:
    def test_add_attributes(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.add_attributes(
            attribute_inputs=[
                AttributeInput(
                    attribute_type=AttributeType.FLAG,
                    attribute_name_en="weather_checked",
                    attribute_name_ja="天気確認済み",
                    attribute_id="weather_checked_attr",
                    label_name_en=["car", "bus"],
                ),
                AttributeInput(
                    attribute_type=AttributeType.TEXT,
                    attribute_name_en="note2",
                    label_id=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                ),
            ],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_attributes = service.api.last_put["additionals"][-2:]
        assert [attribute["additional_data_definition_id"] for attribute in added_attributes] == ["weather_checked_attr", added_attributes[1]["additional_data_definition_id"]]
        assert [attribute["type"] for attribute in added_attributes] == ["flag", "text"]

        car_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "car_label_id")
        bike_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        bus_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert "weather_checked_attr" in car_label["additional_data_definitions"]
        assert "weather_checked_attr" in bus_label["additional_data_definitions"]
        assert added_attributes[1]["additional_data_definition_id"] in bike_label["additional_data_definitions"]
        assert "以下の属性を追加しました。" in service.api.last_put["comment"]

    def test_add_attributes__empty_inputs(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_attributes(attribute_inputs=[])

    def test_add_attributes__duplicated_input_attribute_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_attributes(
                attribute_inputs=[
                    AttributeInput(attribute_type=AttributeType.FLAG, attribute_name_en="weather_checked", label_name_en=["car"]),
                    AttributeInput(attribute_type=AttributeType.TEXT, attribute_name_en="weather_checked", label_name_en=["bus"]),
                ]
            )

    def test_add_attributes__duplicated_input_attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_attributes(
                attribute_inputs=[
                    AttributeInput(attribute_type=AttributeType.FLAG, attribute_name_en="weather_checked", attribute_id="dup_id", label_name_en=["car"]),
                    AttributeInput(attribute_type=AttributeType.TEXT, attribute_name_en="note2", attribute_id="dup_id", label_name_en=["bus"]),
                ]
            )

    def test_add_attributes__duplicated_existing_attribute_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_attributes(
                attribute_inputs=[
                    AttributeInput(attribute_type=AttributeType.COMMENT, attribute_name_en="comment", label_name_en=["car"]),
                ]
            )

    def test_add_attributes__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributesMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.add_attributes(
            attribute_inputs=[
                AttributeInput(attribute_type=AttributeType.FLAG, attribute_name_en="weather_checked", label_name_en=["car"]),
                AttributeInput(attribute_type=AttributeType.TEXT, attribute_name_en="note2", label_name_en=["bus"]),
            ]
        )

        assert result is False
        assert service.api.last_put is None


class TestReadAttributesJson:
    def test_read_attributes_json(self) -> None:
        actual = read_attributes_json(
            '[{"attribute_type":"flag","attribute_name_en":"weather_checked","attribute_name_ja":"天気確認済み","attribute_id":"weather_checked_attr","label_name_en":["car","bus"]},'
            '{"attribute_type":"text","attribute_name_en":"note2","label_id":["car_label_id"]}]'
        )

        assert actual == [
            AttributeInput(
                attribute_type=AttributeType.FLAG,
                attribute_name_en="weather_checked",
                attribute_name_ja="天気確認済み",
                attribute_id="weather_checked_attr",
                label_name_en=["car", "bus"],
            ),
            AttributeInput(
                attribute_type=AttributeType.TEXT,
                attribute_name_en="note2",
                label_id=["car_label_id"],
            ),
        ]

    def test_attribute_input__invalid_attribute_type(self) -> None:
        with pytest.raises(ValidationError):
            AttributeInput(attribute_type=cast(Any, "select"), attribute_name_en="type2", label_name_en=["car"])

    def test_read_attributes_json__attribute_name_en_required(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","label_name_en":["car"]}]')

    def test_read_attributes_json__attribute_type_must_be_valid(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"select","attribute_name_en":"type2","label_name_en":["car"]}]')

    def test_read_attributes_json__label_name_en_and_label_id_are_mutually_exclusive(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_en":["car"],"label_id":["car_label_id"]}]')

    def test_read_attributes_json__label_name_en_must_be_unique(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_type":"flag","attribute_name_en":"weather_checked","label_name_en":["car","car"]}]')
