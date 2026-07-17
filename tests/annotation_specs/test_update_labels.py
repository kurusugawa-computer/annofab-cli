from __future__ import annotations

import json
from pathlib import Path

import pandas
import pytest

from annofabcli.annotation_specs.update_labels import (
    LabelUpdateInput,
    build_request_body_for_update_labels,
    read_labels_csv,
    read_labels_json,
    resolve_label_update_inputs,
    validate_label_update_inputs,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    loaded_annotation_specs["labels"][0]["field_values"] = {
        "margin_of_error_tolerance": {
            "_type": "MarginOfErrorTolerance",
            "max_pixel": 3,
        }
    }
    return loaded_annotation_specs


class TestBuildRequestBodyForUpdateLabels:
    def test_build_request_body_for_update_labels(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_label_update_inputs(
            annotation_specs,
            label_update_inputs=[
                LabelUpdateInput(
                    label_name_en="car",
                    label_name_ja="車",
                    color="#123456",
                    keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                    field_values={
                        "minimum_size_2d_with_default_insert_position": {
                            "_type": "MinimumSize2dWithDefaultInsertPosition",
                            "min_warn_rule": {"_type": "And"},
                            "min_width": 16,
                            "min_height": 8,
                            "position_for_minimum_bounding_box_insertion": None,
                        }
                    },
                ),
                LabelUpdateInput(label_id="40f7796b-3722-4eed-9c0c-04a27f9165d2", field_values_operation="replace"),
            ],
        )

        actual = build_request_body_for_update_labels(
            annotation_specs,
            resolved_label_update_inputs=resolved_inputs,
            comment=None,
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["label_name"]["messages"] == [
            {"lang": "ja-JP", "message": "車"},
            {"lang": "en-US", "message": "car"},
        ]
        assert car_label["annotation_type"] == "bounding_box"
        assert car_label["color"] == {"red": 18, "green": 52, "blue": 86}
        assert car_label["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]
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
        assert bike_label["field_values"] == {}
        assert actual["comment"].startswith("以下のラベル情報を更新しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_update_labels__replace_field_values(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_label_update_inputs(
            annotation_specs,
            label_update_inputs=[
                LabelUpdateInput(
                    label_name_en="car",
                    field_values={"display_line_direction": {"_type": "DisplayLineDirection", "value": True}},
                    field_values_operation="replace",
                )
            ],
        )

        actual = build_request_body_for_update_labels(
            annotation_specs,
            resolved_label_update_inputs=resolved_inputs,
            comment="custom",
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {"display_line_direction": {"_type": "DisplayLineDirection", "value": True}}
        assert actual["comment"] == "custom"

    def test_build_request_body_for_update_labels__preserves_label_name_metadata(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["label_name"] = {
            "messages": [
                {"lang": "en-US", "message": "car"},
                {"lang": "ja-JP", "message": "car"},
                {"lang": "fr-FR", "message": "voiture"},
            ],
            "default_lang": "en-US",
        }
        resolved_inputs = resolve_label_update_inputs(
            annotation_specs,
            label_update_inputs=[LabelUpdateInput(label_name_en="car", label_name_ja="車")],
        )

        actual = build_request_body_for_update_labels(
            annotation_specs,
            resolved_label_update_inputs=resolved_inputs,
            comment=None,
        )

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["label_name"] == {
            "messages": [
                {"lang": "en-US", "message": "car"},
                {"lang": "ja-JP", "message": "車"},
                {"lang": "fr-FR", "message": "voiture"},
            ],
            "default_lang": "en-US",
        }

    def test_build_request_body_for_update_labels__invalid_color(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_label_update_inputs(
            annotation_specs,
            label_update_inputs=[LabelUpdateInput(label_name_en="car", color="red")],
        )

        with pytest.raises(ValueError):
            build_request_body_for_update_labels(
                annotation_specs,
                resolved_label_update_inputs=resolved_inputs,
                comment=None,
            )


class TestResolveLabelUpdateInputs:
    def test_resolve_label_update_inputs__label_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_label_update_inputs(
                annotation_specs,
                label_update_inputs=[LabelUpdateInput(label_name_en="not-found", label_name_ja="dummy")],
            )

    def test_resolve_label_update_inputs__same_label_by_different_keys(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_label_update_inputs(
                annotation_specs,
                label_update_inputs=[
                    LabelUpdateInput(label_id="car_label_id", label_name_ja="車"),
                    LabelUpdateInput(label_name_en="car", color="#123456"),
                ],
            )


class TestLabelUpdateInputs:
    def test_validate_label_update_inputs__duplicated_label_id(self) -> None:
        with pytest.raises(ValueError):
            validate_label_update_inputs(
                [
                    LabelUpdateInput(label_id="car", label_name_ja="車"),
                    LabelUpdateInput(label_id="car", color="#123456"),
                ]
            )

    def test_validate_label_update_inputs__empty(self) -> None:
        with pytest.raises(ValueError):
            validate_label_update_inputs([])


class TestReadLabels:
    def test_read_labels_json(self) -> None:
        actual = read_labels_json(
            '[{"label_name_en":"car","label_name_ja":"車","color":"#123456",'
            '"keybind":{"alt":false,"code":"Digit1","ctrl":true,"shift":false},'
            '"field_values":{"margin_of_error_tolerance":{"max_pixel":5,"_type":"MarginOfErrorTolerance"}}},'
            '{"label_id":"bike","field_values_operation":"replace"}]'
        )

        assert actual == [
            LabelUpdateInput(
                label_name_en="car",
                label_name_ja="車",
                color="#123456",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                field_values={"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
            ),
            LabelUpdateInput(label_id="bike", field_values_operation="replace"),
        ]

    def test_read_labels_json__annotation_type_is_not_allowed(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_en":"car","label_name_ja":"車","annotation_type":"bounding_box"}]')

    def test_read_labels_json__target_required(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_ja":"車"}]')

    def test_read_labels_json__field_values_operation_merge_requires_field_values(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_en":"car","field_values_operation":"merge"}]')

    def test_read_labels_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "labels.csv"
        df = pandas.DataFrame(
            [
                {
                    "label_name_en": "car",
                    "label_name_ja": "車",
                    "color": "#123456",
                    "keybind": '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}',
                    "field_values": '{"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}}',
                },
                {"label_id": "bike", "field_values_operation": "replace"},
            ]
        )
        df.to_csv(csv_path, index=False)

        actual = read_labels_csv(csv_path)

        assert actual == [
            LabelUpdateInput(
                label_name_en="car",
                label_name_ja="車",
                color="#123456",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                field_values={"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
            ),
            LabelUpdateInput(label_id="bike", field_values_operation="replace"),
        ]
