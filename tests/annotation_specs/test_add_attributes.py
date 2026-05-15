from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from annofabcli.annotation_specs.add_attribute import AttributeType
from annofabcli.annotation_specs.add_attributes import AddAttributesMain, AttributeInput, read_attributes_json


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
