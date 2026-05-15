from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import update_label_field_values
from annofabcli.annotation_specs.update_label_field_values import (
    build_request_body_for_update_label_field_values,
    resolve_update_label_field_values_input,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveUpdateLabelFieldValuesInput:
    def test_resolve_update_label_field_values_input__label_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_update_label_field_values_input(
                annotation_specs,
                label_ids=["not-found"],
                label_name_ens=[],
            )


class TestBuildRequestBodyForUpdateLabelFieldValues:
    def test_build_request_body_for_update_label_field_values__merge(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        resolved_input = resolve_update_label_field_values_input(
            annotation_specs,
            label_ids=[],
            label_name_ens=["car", "bike"],
        )

        actual = build_request_body_for_update_label_field_values(
            annotation_specs,
            resolved_input=resolved_input,
            field_values={
                "minimum_size_2d_with_default_insert_position": {
                    "_type": "MinimumSize2dWithDefaultInsertPosition",
                    "min_warn_rule": {"_type": "And"},
                    "min_width": 16,
                    "min_height": 8,
                    "position_for_minimum_bounding_box_insertion": None,
                }
            },
            replace=False,
            clear=False,
            comment=None,
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            },
            "minimum_size_2d_with_default_insert_position": {
                "_type": "MinimumSize2dWithDefaultInsertPosition",
                "min_warn_rule": {"_type": "And"},
                "min_width": 16,
                "min_height": 8,
                "position_for_minimum_bounding_box_insertion": None,
            },
        }
        bike_label = next(label for label in actual["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert bike_label["field_values"] == {
            "minimum_size_2d_with_default_insert_position": {
                "_type": "MinimumSize2dWithDefaultInsertPosition",
                "min_warn_rule": {"_type": "And"},
                "min_width": 16,
                "min_height": 8,
                "position_for_minimum_bounding_box_insertion": None,
            }
        }
        assert "field_values を更新しました" in actual["comment"]
        assert "field_value_keys: minimum_size_2d_with_default_insert_position" in actual["comment"]
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_update_label_field_values__replace(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        resolved_input = resolve_update_label_field_values_input(
            annotation_specs,
            label_ids=["car_label_id"],
            label_name_ens=[],
        )

        actual = build_request_body_for_update_label_field_values(
            annotation_specs,
            resolved_input=resolved_input,
            field_values={
                "display_line_direction": {
                    "_type": "DisplayLineDirection",
                    "value": True,
                }
            },
            replace=True,
            clear=False,
            comment="custom",
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {
            "display_line_direction": {
                "_type": "DisplayLineDirection",
                "value": True,
            }
        }
        assert actual["comment"] == "custom"

    def test_build_request_body_for_update_label_field_values__clear(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        resolved_input = resolve_update_label_field_values_input(
            annotation_specs,
            label_ids=[],
            label_name_ens=["car"],
        )

        actual = build_request_body_for_update_label_field_values(
            annotation_specs,
            resolved_input=resolved_input,
            field_values=None,
            replace=False,
            clear=True,
            comment=None,
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {}
        assert "field_values をクリアしました" in actual["comment"]


class TestValidateFieldValuesInput:
    def test_field_values_json_is_not_object(self) -> None:
        with pytest.raises(TypeError):
            update_label_field_values.validate_field_values_input([{"_type": "Dummy"}])
