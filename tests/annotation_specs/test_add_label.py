from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_label
from annofabcli.annotation_specs.add_label import (
    AUTO_COLOR_PALETTE_HEX,
    DEFAULT_SEGMENTATION_FIELD_VALUES,
    build_request_body_for_add_label,
    collect_label_colors,
    create_auto_color,
    resolve_new_label_input,
)
from annofabcli.annotation_specs.color import RgbColor, hex_to_rgb

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestColor:
    def test_auto_color_palette_hex__is_hex_color_code(self) -> None:
        assert all(color_code.startswith("#") and len(color_code) == 7 for color_code in AUTO_COLOR_PALETTE_HEX)

    def test_create_auto_color(self, annotation_specs: dict) -> None:
        colors: list[RgbColor] = collect_label_colors(annotation_specs["labels"])
        actual = create_auto_color(colors)
        assert actual == {"red": 255, "green": 85, "blue": 0}

    def test_create_auto_color__uses_extended_vivid_palette(self) -> None:
        colors: list[RgbColor] = [
            {"red": 255, "green": 0, "blue": 0},
            {"red": 255, "green": 85, "blue": 0},
            {"red": 255, "green": 170, "blue": 0},
            {"red": 255, "green": 255, "blue": 0},
            {"red": 170, "green": 255, "blue": 0},
            {"red": 85, "green": 255, "blue": 0},
            {"red": 0, "green": 255, "blue": 0},
            {"red": 0, "green": 255, "blue": 85},
            {"red": 0, "green": 255, "blue": 170},
            {"red": 0, "green": 255, "blue": 255},
        ]

        actual = create_auto_color(colors)

        assert actual == {"red": 0, "green": 170, "blue": 255}

    def test_create_auto_color__returns_least_used_palette_color_when_all_palette_colors_are_used(self) -> None:
        colors: list[RgbColor] = [hex_to_rgb(color_code) for color_code in AUTO_COLOR_PALETTE_HEX]
        colors.append({"red": 255, "green": 0, "blue": 0})

        actual = create_auto_color(colors)

        assert actual == {"red": 255, "green": 85, "blue": 0}


class TestResolveNewLabelInput:
    def test_resolve_new_label_input(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja="歩行者",
            color_code="#00CCFF",
            field_values=None,
        )

        assert actual.label_id == "pedestrian_label_id"
        assert actual.new_label["annotation_type"] == "bounding_box"
        assert actual.new_label["color"] == {"red": 0, "green": 204, "blue": 255}

    def test_resolve_new_label_input__label_id_is_uuidv4_when_not_specified(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id=None,
            label_name_ja=None,
            color_code="#00CCFF",
            field_values=None,
        )

        assert str(uuid.UUID(actual.label_id, version=4)) == actual.label_id
        assert actual.new_label["label_name"]["messages"][1]["message"] == "pedestrian"

    def test_resolve_new_label_input__auto_color(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code=None,
            field_values=None,
        )

        assert actual.new_label["color"] == {"red": 255, "green": 85, "blue": 0}

    def test_resolve_new_label_input__field_values(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values={
                "margin_of_error_tolerance": {
                    "max_pixel": 5,
                    "_type": "MarginOfErrorTolerance",
                }
            },
        )

        assert actual.new_label["field_values"] == {
            "margin_of_error_tolerance": {
                "max_pixel": 5,
                "_type": "MarginOfErrorTolerance",
            }
        }

    def test_resolve_new_label_input__keybind(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
            field_values=None,
        )

        assert actual.new_label["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]

    def test_resolve_new_label_input__segmentation_has_default_field_values(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="road",
            annotation_type="segmentation",
            label_id="road_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values=None,
        )

        assert actual.new_label["field_values"] == DEFAULT_SEGMENTATION_FIELD_VALUES

    def test_resolve_new_label_input__segmentation_v2_merges_default_field_values(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="road",
            annotation_type="segmentation_v2",
            label_id="road_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values={
                "margin_of_error_tolerance": {
                    "max_pixel": 5,
                    "_type": "MarginOfErrorTolerance",
                }
            },
        )

        assert actual.new_label["field_values"] == {
            **DEFAULT_SEGMENTATION_FIELD_VALUES,
            "margin_of_error_tolerance": {
                "max_pixel": 5,
                "_type": "MarginOfErrorTolerance",
            },
        }

    def test_resolve_new_label_input__segmentation_overwrites_annotation_editor_feature(self, annotation_specs: dict) -> None:
        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="road",
            annotation_type="segmentation",
            label_id="road_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values={
                "annotation_editor_feature": {
                    "_type": "AnnotationEditorFeature",
                    "append": False,
                }
            },
        )

        assert actual.new_label["field_values"] == {
            "annotation_editor_feature": {
                "_type": "AnnotationEditorFeature",
                "append": False,
            }
        }

    def test_resolve_new_label_input__does_not_inherit_existing_label_fields(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {"existing": {"_type": "Dummy"}}
        annotation_specs["labels"][0]["bounding_box_metadata"] = {"value": True}
        annotation_specs["labels"][0]["segmentation_metadata"] = {"value": True}
        annotation_specs["labels"][0]["annotation_editor_feature"] = {"append": True, "erase": True}
        annotation_specs["labels"][0]["allow_out_of_image_bounds"] = True

        actual = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values=None,
        )

        assert actual.new_label["field_values"] == {}
        assert actual.new_label["additional_data_definitions"] == []
        assert "bounding_box_metadata" not in actual.new_label
        assert "segmentation_metadata" not in actual.new_label
        assert "annotation_editor_feature" not in actual.new_label
        assert "allow_out_of_image_bounds" not in actual.new_label

    def test_resolve_new_label_input__duplicated_label_id(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_new_label_input(
                annotation_specs,
                label_name_en="pedestrian",
                annotation_type="bounding_box",
                label_id="car_label_id",
                label_name_ja=None,
                color_code="#00CCFF",
                field_values=None,
            )

    def test_resolve_new_label_input__duplicated_label_name(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_new_label_input(
                annotation_specs,
                label_name_en="car",
                annotation_type="bounding_box",
                label_id="new_label_id",
                label_name_ja=None,
                color_code="#00CCFF",
                field_values=None,
            )

    def test_resolve_new_label_input__invalid_color_code(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_new_label_input(
                annotation_specs,
                label_name_en="pedestrian",
                annotation_type="bounding_box",
                label_id="pedestrian_label_id",
                label_name_ja=None,
                color_code="00CCFF",
                field_values=None,
            )


class TestBuildRequestBodyForAddLabel:
    def test_build_request_body_for_add_label__custom_comment(self, annotation_specs: dict) -> None:
        resolved_input = resolve_new_label_input(
            annotation_specs,
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            field_values=None,
        )

        actual = build_request_body_for_add_label(
            annotation_specs,
            resolved_new_label_input=resolved_input,
            label_name_en="pedestrian",
            comment="custom",
        )

        assert actual["labels"][-1]["label_id"] == "pedestrian_label_id"
        assert actual["comment"] == "custom"
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"


class TestValidateFieldValuesInput:
    def test_field_values_json_is_not_object(self) -> None:
        with pytest.raises(TypeError):
            add_label.validate_field_values_input([{"_type": "Dummy"}])


class TestValidateKeybindInput:
    def test_keybind_object_is_normalized_to_list(self) -> None:
        actual = add_label.validate_keybind_input({"code": "Digit1", "ctrl": True})

        assert actual == {"alt": False, "code": "Digit1", "ctrl": True, "shift": False}

    def test_keybind_code_is_required(self) -> None:
        with pytest.raises(ValueError):
            add_label.validate_keybind_input({"ctrl": True})
