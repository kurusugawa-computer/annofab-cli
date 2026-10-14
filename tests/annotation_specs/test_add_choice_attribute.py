from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

import pytest
from annofabapi.util.annotation_specs import get_attribute_name_en

from annofabcli.annotation_specs.add_choice_attribute import (
    ResolvedChoiceAttributeInput,
    build_choices,
    build_request_body_for_add_choice_attribute,
    read_choices_csv,
    read_choices_json,
    resolve_choice_attribute_input,
)
from annofabcli.annotation_specs.utils import create_name

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestReadChoicesJson:
    def test_read_choices_json(self) -> None:
        actual = read_choices_json('[{"choice_id":"front","choice_name_en":"front","choice_name_ja":"前","is_default":true,"keybind":{"alt":false,"code":"Digit1","ctrl":true,"shift":false}}]')
        assert actual[0].choice_id == "front"
        assert actual[0].choice_name_en == "front"
        assert actual[0].choice_name_ja == "前"
        assert actual[0].is_default is True
        assert actual[0].keybind == {"alt": False, "code": "Digit1", "ctrl": True, "shift": False}

    def test_read_choices_json__without_choice_id(self) -> None:
        actual = read_choices_json('[{"choice_name_en":"front"}]')
        assert actual[0].choice_id is None
        assert actual[0].is_default is False

    def test_read_choices_json__not_list(self) -> None:
        with pytest.raises(TypeError):
            read_choices_json('{"choice_name_en":"front"}')

    def test_read_choices_json__missing_choice_name_en(self) -> None:
        with pytest.raises(ValueError):
            read_choices_json('[{"choice_id":"front"}]')

    def test_build_choices__duplicated_choice_id(self) -> None:
        choices = read_choices_json('[{"choice_id":"dup","choice_name_en":"front"},{"choice_id":"dup","choice_name_en":"rear"}]')
        with pytest.raises(ValueError):
            build_choices(choices)

    def test_build_choices__multiple_default(self) -> None:
        choices = read_choices_json('[{"choice_name_en":"front","is_default":true},{"choice_name_en":"rear","is_default":true}]')
        with pytest.raises(ValueError):
            build_choices(choices)


class TestReadChoicesCsv:
    def test_read_choices_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text(
            "choice_id,choice_name_en,choice_name_ja,is_default\nfront,front,前,true\n,rear,,false\n",
            encoding="utf-8",
        )

        actual = read_choices_csv(csv_path)
        assert len(actual) == 2
        assert actual[0].choice_id == "front"
        assert actual[0].is_default is True
        assert actual[1].choice_id is None
        assert actual[1].choice_name_ja is None

    def test_read_choices_csv__required_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text(
            "choice_id,is_default\nfront,true\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError):
            read_choices_csv(csv_path)

    def test_read_choices_csv__invalid_is_default(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text(
            "choice_id,choice_name_en,choice_name_ja,is_default\nfront,front,前,invalid\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError):
            read_choices_csv(csv_path)


class TestResolveChoiceAttributeInput:
    def test_resolve_choice_attribute_input(self, annotation_specs: dict) -> None:
        actual = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="choice",
            attribute_name_en="weather",
            attribute_name_ja="天気",
            attribute_id="weather_attr",
            choice_inputs=read_choices_json('[{"choice_id":"sunny","choice_name_en":"sunny","choice_name_ja":"晴れ","is_default":true},{"choice_name_en":"cloudy"}]'),
            label_ids=[],
            label_name_ens=["car"],
            read_only=True,
            keybind={"alt": False, "code": "Digit2", "ctrl": True, "shift": False},
        )

        assert actual.new_attribute["additional_data_definition_id"] == "weather_attr"
        assert actual.new_attribute["type"] == "choice"
        assert actual.new_attribute["default"] == "sunny"
        assert actual.new_attribute["read_only"] is True
        assert actual.new_attribute["keybind"] == [{"alt": False, "code": "Digit2", "ctrl": True, "shift": False}]
        assert len(actual.new_attribute["choices"]) == 2
        assert [label["label_id"] for label in actual.target_labels] == ["car_label_id"]

    def test_resolve_choice_attribute_input__attribute_id_is_uuidv4_when_not_specified(self, annotation_specs: dict) -> None:
        actual = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="select",
            attribute_name_en="weather_uuid",
            attribute_name_ja=None,
            attribute_id=None,
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}]'),
            label_ids=["car_label_id"],
            label_name_ens=[],
        )

        generated_attribute_id = actual.new_attribute["additional_data_definition_id"]
        assert str(uuid.UUID(generated_attribute_id, version=4)) == generated_attribute_id

    def test_resolve_choice_attribute_input__label_name_ens_can_be_none(self, annotation_specs: dict) -> None:
        actual = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="select",
            attribute_name_en="weather3",
            attribute_name_ja=None,
            attribute_id="weather_attr3",
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}]'),
            label_ids=["car_label_id"],
            label_name_ens=None,
        )

        assert [label["label_id"] for label in actual.target_labels] == ["car_label_id"]

    def test_resolve_choice_attribute_input__duplicated_attribute_id(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_choice_attribute_input(
                annotation_specs,
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=["car_label_id"],
                label_name_ens=[],
            )

    def test_resolve_choice_attribute_input__duplicated_attribute_name__warning(self, annotation_specs: dict, caplog: pytest.LogCaptureFixture) -> None:
        actual = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="choice",
            attribute_name_en="type",
            attribute_name_ja=None,
            attribute_id="weather_attr",
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}]'),
            label_ids=["car_label_id"],
            label_name_ens=[],
        )

        assert actual.duplicated_name_attribute_ids == ["71620647-98cf-48ad-b43b-4af425a24f32"]
        assert "属性名(英語)='type' の属性は既に存在しますが、処理を継続します。" in caplog.text

    def test_resolve_choice_attribute_input__ambiguous_label_name(self, annotation_specs: dict) -> None:
        duplicated_label = json.loads(json.dumps(annotation_specs["labels"][0]))
        duplicated_label["label_id"] = "duplicated-id"
        annotation_specs["labels"].append(duplicated_label)

        with pytest.raises(ValueError):
            resolve_choice_attribute_input(
                annotation_specs,
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="weather_attr",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=[],
                label_name_ens=["car"],
            )

    def test_resolve_choice_attribute_input__label_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_choice_attribute_input(
                annotation_specs,
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="weather_attr",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=["not-found"],
                label_name_ens=[],
            )


class TestBuildRequestBodyForAddChoiceAttribute:
    def test_build_request_body_for_add_choice_attribute(self, annotation_specs: dict) -> None:
        resolved_input = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="choice",
            attribute_name_en="weather",
            attribute_name_ja="天気",
            attribute_id="weather_attr",
            choice_inputs=read_choices_json('[{"choice_id":"sunny","choice_name_en":"sunny","choice_name_ja":"晴れ","is_default":true},{"choice_name_en":"cloudy"}]'),
            label_ids=[],
            label_name_ens=["car"],
            read_only=True,
        )

        actual = build_request_body_for_add_choice_attribute(
            annotation_specs,
            resolved_choice_attribute_input=resolved_input,
            attribute_name_en="weather",
            comment=None,
        )

        additionals = actual["additionals"]
        labels = actual["labels"]
        added_attribute = additionals[-1]
        assert added_attribute["additional_data_definition_id"] == "weather_attr"
        assert added_attribute["type"] == "choice"
        assert added_attribute["default"] == "sunny"
        assert added_attribute["read_only"] is True
        assert len(added_attribute["choices"]) == 2
        assert added_attribute["choices"][0]["keybind"] == []

        car_label = next(label for label in labels if label["label_id"] == "car_label_id")
        bike_label = next(label for label in labels if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert "weather_attr" in car_label["additional_data_definitions"]
        assert "weather_attr" not in bike_label["additional_data_definitions"]
        assert actual["comment"].startswith("以下の選択肢系属性を追加しました。")

    def test_build_request_body_for_add_choice_attribute__default_empty(self, annotation_specs: dict) -> None:
        resolved_input = resolve_choice_attribute_input(
            annotation_specs,
            attribute_type="select",
            attribute_name_en="weather2",
            attribute_name_ja=None,
            attribute_id="weather_attr2",
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}]'),
            label_ids=["car_label_id"],
            label_name_ens=[],
        )

        actual = build_request_body_for_add_choice_attribute(
            annotation_specs,
            resolved_choice_attribute_input=resolved_input,
            attribute_name_en="weather2",
            comment="custom",
        )

        added_attribute = actual["additionals"][-1]
        assert added_attribute["default"] is None
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
    resolved = ResolvedChoiceAttributeInput(target_labels=labels, new_attribute=new_attribute, duplicated_name_attribute_ids=[])
    actual = build_request_body_for_add_choice_attribute(annotation_specs, resolved_choice_attribute_input=resolved, attribute_name_en="new", comment=None, before_attribute_name_en=before)
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
    resolved = ResolvedChoiceAttributeInput(target_labels=labels, new_attribute={"additional_data_definition_id": "new"}, duplicated_name_attribute_ids=[])
    with pytest.raises(ValueError):
        build_request_body_for_add_choice_attribute(
            annotation_specs, resolved_choice_attribute_input=resolved, attribute_name_en="new", comment=None, before_attribute_name_en="missing" if error == "missing" else "anchor"
        )
    assert annotation_specs == original
