from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from annofabapi.util.annotation_specs import get_attribute_name_en

from annofabcli.annotation_specs.add_attribute import (
    AddAttributeMain,
    ResolvedAttributeInput,
    build_request_body_for_add_attribute,
    parse_default_value,
    resolve_attribute_input,
)
from annofabcli.annotation_specs.utils import create_name

data_dir = Path("./tests/data/annotation_specs")


class TestParseDefaultValue:
    def test_parse_default_value__flag(self) -> None:
        assert parse_default_value("flag", "true") is True
        assert parse_default_value("flag", "false") is False

    def test_parse_default_value__integer(self) -> None:
        assert parse_default_value("integer", "123") == 123

    def test_parse_default_value__text(self) -> None:
        assert parse_default_value("text", "memo") == "memo"

    def test_parse_default_value__invalid_flag(self) -> None:
        with pytest.raises(ValueError):
            parse_default_value("flag", "yes")

    def test_parse_default_value__invalid_integer(self) -> None:
        with pytest.raises(ValueError):
            parse_default_value("integer", "abc")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveAttributeInput:
    def test_resolve_attribute_input(self, annotation_specs: dict) -> None:
        actual = resolve_attribute_input(
            annotation_specs,
            attribute_type="flag",
            attribute_name_en="weather_checked",
            attribute_name_ja="天気確認済み",
            attribute_id="weather_checked_attr",
            label_ids=[],
            label_name_ens=["car"],
            read_only=True,
            default_value="true",
            keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
        )

        assert actual.new_attribute["additional_data_definition_id"] == "weather_checked_attr"
        assert actual.new_attribute["type"] == "flag"
        assert actual.new_attribute["read_only"] is True
        assert actual.new_attribute["default"] is True
        assert actual.new_attribute["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]
        assert [label["label_id"] for label in actual.target_labels] == ["car_label_id"]
        assert actual.duplicated_name_attribute_ids == []

    def test_resolve_attribute_input__duplicated_attribute_id(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_input(
                annotation_specs,
                attribute_type="flag",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                label_ids=["car_label_id"],
                label_name_ens=[],
            )


class TestBuildRequestBodyForAddAttribute:
    def test_build_request_body_for_add_attribute(self, annotation_specs: dict) -> None:
        resolved_attribute_input = resolve_attribute_input(
            annotation_specs,
            attribute_type="flag",
            attribute_name_en="weather_checked",
            attribute_name_ja="天気確認済み",
            attribute_id="weather_checked_attr",
            label_ids=[],
            label_name_ens=["car"],
            read_only=True,
            default_value="true",
        )

        actual = build_request_body_for_add_attribute(
            annotation_specs,
            resolved_attribute_input=resolved_attribute_input,
            attribute_name_en="weather_checked",
            comment=None,
        )

        assert actual["additionals"][-1]["additional_data_definition_id"] == "weather_checked_attr"
        assert actual["additionals"][-1]["type"] == "flag"
        assert actual["additionals"][-1]["read_only"] is True
        assert actual["additionals"][-1]["default"] is True
        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        bike_label = next(label for label in actual["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert "weather_checked_attr" in car_label["additional_data_definitions"]
        assert "weather_checked_attr" not in bike_label["additional_data_definitions"]
        assert "以下の属性を追加しました。" in actual["comment"]
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert all(additional["additional_data_definition_id"] != "weather_checked_attr" for additional in annotation_specs["additionals"])

    def test_build_request_body_for_add_attribute__custom_comment(self, annotation_specs: dict) -> None:
        resolved_attribute_input = resolve_attribute_input(
            annotation_specs,
            attribute_type="text",
            attribute_name_en="note",
            attribute_name_ja="メモ",
            attribute_id="note_attr",
            label_ids=["car_label_id"],
            label_name_ens=[],
        )

        actual = build_request_body_for_add_attribute(
            annotation_specs,
            resolved_attribute_input=resolved_attribute_input,
            attribute_name_en="note",
            comment="custom",
        )

        assert actual["comment"] == "custom"


@pytest.mark.parametrize("before", [None, "anchor"])
def test_add_before_attribute_in_multiple_labels(annotation_specs: dict, before: str | None) -> None:
    attributes = annotation_specs["additionals"]
    anchor_id = attributes[0]["additional_data_definition_id"]
    other_id = attributes[1]["additional_data_definition_id"]
    attributes[0]["name"] = create_name("anchor", None)
    labels = annotation_specs["labels"][:2]
    labels[0]["additional_data_definitions"] = [other_id, anchor_id]
    labels[1]["additional_data_definitions"] = [anchor_id, other_id]
    original = deepcopy(annotation_specs)
    new_attribute = {"additional_data_definition_id": "new", "name": create_name("new", None)}
    resolved = ResolvedAttributeInput(target_labels=labels, new_attribute=new_attribute, duplicated_name_attribute_ids=[])
    actual = build_request_body_for_add_attribute(annotation_specs, resolved_attribute_input=resolved, attribute_name_en="new", comment=None, before_attribute_name_en=before)
    assert [get_attribute_name_en(a) for a in actual["additionals"]].index("new") == (0 if before else len(attributes))
    assert actual["labels"][0]["additional_data_definitions"] == ([other_id, "new", anchor_id] if before else [other_id, anchor_id, "new"])
    assert actual["labels"][1]["additional_data_definitions"] == (["new", anchor_id, other_id] if before else [anchor_id, other_id, "new"])
    assert annotation_specs == original


@pytest.mark.parametrize("error", ["missing", "ambiguous", "missing_in_one_label"])
def test_invalid_before_attribute_does_not_modify_specs(annotation_specs: dict, error: str) -> None:
    attributes = annotation_specs["additionals"]
    anchor_id = attributes[0]["additional_data_definition_id"]
    attributes[0]["name"] = create_name("anchor", None)
    labels = annotation_specs["labels"][:2]
    for label in labels:
        label["additional_data_definitions"] = [anchor_id]
    if error == "ambiguous":
        attributes.append({"additional_data_definition_id": "duplicate", "name": create_name("anchor", None)})
    elif error == "missing_in_one_label":
        labels[1]["additional_data_definitions"] = []
    original = deepcopy(annotation_specs)
    resolved = ResolvedAttributeInput(target_labels=labels, new_attribute={"additional_data_definition_id": "new"}, duplicated_name_attribute_ids=[])
    with pytest.raises(ValueError):
        build_request_body_for_add_attribute(
            annotation_specs, resolved_attribute_input=resolved, attribute_name_en="new", comment=None, before_attribute_name_en="missing" if error == "missing" else "anchor"
        )
    assert annotation_specs == original


def test_missing_anchor_in_one_label_prevents_api_update(annotation_specs: dict) -> None:
    service = MagicMock()
    service.api.get_annotation_specs.return_value = (annotation_specs, None)
    command = AddAttributeMain(service, project_id="prj1", all_yes=True)
    # carにはcommentがあるが、bikeには属性がない。
    with pytest.raises(ValueError):
        command.add_attribute(
            attribute_type="flag", attribute_name_en="new", attribute_name_ja=None, attribute_id="new", label_ids=None, label_name_ens=["car", "bike"], before_attribute_name_en="comment"
        )
    service.api.put_annotation_specs.assert_not_called()
