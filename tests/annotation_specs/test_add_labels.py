from __future__ import annotations

import json
from pathlib import Path

import pandas
import pytest

from annofabcli.annotation_specs.add_label import DEFAULT_SEGMENTATION_FIELD_VALUES
from annofabcli.annotation_specs.add_labels import (
    LabelInput,
    build_request_body_for_add_labels,
    create_label_color,
    create_label_inputs_from_name_ens,
    parse_annotation_type_in_csv,
    parse_field_values_in_csv,
    parse_keybind_in_csv,
    read_labels_csv,
    read_labels_json,
    resolve_annotation_types,
    validate_label_inputs,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestBuildRequestBodyForAddLabels:
    def test_build_request_body_for_add_labels(self, annotation_specs: dict) -> None:
        actual = build_request_body_for_add_labels(
            annotation_specs,
            resolved_label_inputs=resolve_annotation_types(
                [
                    LabelInput(
                        label_id="pedestrian",
                        label_name_en="pedestrian",
                        label_name_ja="歩行者",
                        color="#123456",
                        keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                        field_values={"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
                    ),
                    LabelInput(label_name_en="bicycle"),
                ],
                annotation_type="bounding_box",
            ),
            comment=None,
        )

        added_labels = actual["labels"][-2:]
        assert [label["label_id"] for label in added_labels] == ["pedestrian", added_labels[1]["label_id"]]
        assert [label["label_name"]["messages"][0]["message"] for label in added_labels] == ["pedestrian", "bicycle"]
        assert [label["label_name"]["messages"][1]["message"] for label in added_labels] == ["歩行者", "bicycle"]
        assert [label["annotation_type"] for label in added_labels] == ["bounding_box", "bounding_box"]
        assert added_labels[0]["color"] == {"red": 18, "green": 52, "blue": 86}
        assert added_labels[1]["color"] == {"red": 255, "green": 85, "blue": 0}
        assert added_labels[0]["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]
        assert added_labels[1]["keybind"] == []
        assert added_labels[0]["field_values"] == {"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}}
        assert added_labels[1]["field_values"] == {}
        assert actual["comment"].startswith("以下のラベルを追加しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_add_labels__invalid_color(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            build_request_body_for_add_labels(
                annotation_specs,
                resolved_label_inputs=resolve_annotation_types(
                    [LabelInput(label_name_en="pedestrian", color="red")],
                    annotation_type="bounding_box",
                ),
                comment=None,
            )

    def test_build_request_body_for_add_labels__duplicated_existing_label_name(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            build_request_body_for_add_labels(
                annotation_specs,
                resolved_label_inputs=resolve_annotation_types(
                    [LabelInput(label_name_en="pedestrian"), LabelInput(label_name_en="car")],
                    annotation_type="bounding_box",
                ),
                comment=None,
            )

    def test_build_request_body_for_add_labels__segmentation_has_default_field_values(self, annotation_specs: dict) -> None:
        actual = build_request_body_for_add_labels(
            annotation_specs,
            resolved_label_inputs=resolve_annotation_types(
                [LabelInput(label_name_en="road"), LabelInput(label_name_en="sidewalk")],
                annotation_type="segmentation_v2",
            ),
            comment=None,
        )

        added_labels = actual["labels"][-2:]
        assert added_labels[0]["field_values"] == DEFAULT_SEGMENTATION_FIELD_VALUES
        assert added_labels[1]["field_values"] == DEFAULT_SEGMENTATION_FIELD_VALUES

    def test_build_request_body_for_add_labels__uses_annotation_type_in_label_inputs(self, annotation_specs: dict) -> None:
        actual = build_request_body_for_add_labels(
            annotation_specs,
            resolved_label_inputs=resolve_annotation_types(
                [
                    LabelInput(label_name_en="road", annotation_type="segmentation_v2"),
                    LabelInput(label_name_en="crosswalk", annotation_type="bounding_box"),
                ],
                annotation_type=None,
            ),
            comment=None,
        )

        added_labels = actual["labels"][-2:]
        assert [label["annotation_type"] for label in added_labels] == ["segmentation_v2", "bounding_box"]
        assert added_labels[0]["field_values"] == DEFAULT_SEGMENTATION_FIELD_VALUES
        assert added_labels[1]["field_values"] == {}


class TestLabelInputs:
    def test_validate_label_inputs__duplicated_input(self) -> None:
        with pytest.raises(ValueError):
            validate_label_inputs([LabelInput(label_name_en="pedestrian"), LabelInput(label_name_en="pedestrian")])

    def test_validate_label_inputs__duplicated_input_label_id(self) -> None:
        with pytest.raises(ValueError):
            validate_label_inputs(
                [
                    LabelInput(label_id="pedestrian", label_name_en="pedestrian"),
                    LabelInput(label_id="pedestrian", label_name_en="bicycle"),
                ]
            )

    def test_validate_label_inputs__empty_label_inputs(self) -> None:
        with pytest.raises(ValueError):
            validate_label_inputs([])

    def test_resolve_annotation_types(self) -> None:
        actual = resolve_annotation_types(
            [
                LabelInput(label_name_en="pedestrian", annotation_type="bounding_box"),
                LabelInput(label_name_en="bicycle"),
            ],
            annotation_type="bounding_box",
        )

        assert actual == [
            LabelInput(label_name_en="pedestrian", annotation_type="bounding_box"),
            LabelInput(label_name_en="bicycle", annotation_type="bounding_box"),
        ]

    def test_resolve_annotation_types__raises_when_annotation_type_is_missing(self) -> None:
        with pytest.raises(ValueError):
            resolve_annotation_types([LabelInput(label_name_en="pedestrian")], annotation_type=None)

    def test_resolve_annotation_types__raises_when_conflicted(self) -> None:
        with pytest.raises(ValueError):
            resolve_annotation_types(
                [LabelInput(label_name_en="pedestrian", annotation_type="polygon")],
                annotation_type="bounding_box",
            )


class TestReadLabels:
    def test_create_label_inputs_from_name_ens(self) -> None:
        actual = create_label_inputs_from_name_ens(["pedestrian", "bicycle"])

        assert actual == [
            LabelInput(label_name_en="pedestrian"),
            LabelInput(label_name_en="bicycle"),
        ]

    def test_read_labels_json(self) -> None:
        actual = read_labels_json(
            '[{"label_id":"pedestrian","label_name_en":"pedestrian","label_name_ja":"歩行者","annotation_type":"bounding_box","color":"#123456",'
            '"keybind":{"alt":false,"code":"Digit1","ctrl":true,"shift":false},'
            '"field_values":{"margin_of_error_tolerance":{"max_pixel":5,"_type":"MarginOfErrorTolerance"}}},{"label_name_en":"bicycle","annotation_type":"polygon"}]'
        )

        assert actual == [
            LabelInput(
                label_id="pedestrian",
                label_name_en="pedestrian",
                label_name_ja="歩行者",
                annotation_type="bounding_box",
                color="#123456",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                field_values={"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
            ),
            LabelInput(label_name_en="bicycle", annotation_type="polygon"),
        ]

    def test_read_labels_json__label_name_en_required(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_ja":"歩行者"}]')

    def test_read_labels_json__invalid_annotation_type(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_en":"pedestrian","annotation_type":"invalid"}]')

    def test_read_labels_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "labels.csv"
        df = pandas.DataFrame(
            [
                {
                    "label_id": "pedestrian",
                    "label_name_en": "pedestrian",
                    "label_name_ja": "歩行者",
                    "annotation_type": "bounding_box",
                    "color": "#123456",
                    "keybind": '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}',
                    "field_values": '{"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}}',
                },
                {"label_name_en": "bicycle", "annotation_type": "polygon"},
            ]
        )
        df.to_csv(csv_path, index=False)

        actual = read_labels_csv(csv_path)

        assert actual == [
            LabelInput(
                label_id="pedestrian",
                label_name_en="pedestrian",
                label_name_ja="歩行者",
                annotation_type="bounding_box",
                color="#123456",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                field_values={"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}},
            ),
            LabelInput(label_name_en="bicycle", annotation_type="polygon"),
        ]

    def test_read_labels_csv__label_name_en_required(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "labels.csv"
        pandas.DataFrame([{"label_id": "pedestrian", "label_name_ja": "歩行者"}]).to_csv(csv_path, index=False)

        with pytest.raises(ValueError):
            read_labels_csv(csv_path)

    def test_create_label_color(self) -> None:
        actual = create_label_color("#123456", [])
        assert actual == {"red": 18, "green": 52, "blue": 86}

    def test_parse_field_values_in_csv(self) -> None:
        actual = parse_field_values_in_csv('{"margin_of_error_tolerance":{"max_pixel":5,"_type":"MarginOfErrorTolerance"}}', index=1)
        assert actual == {"margin_of_error_tolerance": {"max_pixel": 5, "_type": "MarginOfErrorTolerance"}}

    def test_parse_field_values_in_csv__empty(self) -> None:
        assert parse_field_values_in_csv("", index=1) is None

    def test_parse_field_values_in_csv__invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_field_values_in_csv("[]", index=1)

    def test_parse_keybind_in_csv(self) -> None:
        actual = parse_keybind_in_csv('{"alt":false,"code":"Digit1","ctrl":true,"shift":false}', index=1)
        assert actual == {"alt": False, "code": "Digit1", "ctrl": True, "shift": False}

    def test_parse_keybind_in_csv__empty(self) -> None:
        assert parse_keybind_in_csv("", index=1) is None

    def test_parse_keybind_in_csv__invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_keybind_in_csv('"invalid"', index=1)

    def test_parse_annotation_type_in_csv(self) -> None:
        assert parse_annotation_type_in_csv("polygon", index=1) == "polygon"

    def test_parse_annotation_type_in_csv__empty(self) -> None:
        assert parse_annotation_type_in_csv("", index=1) is None

    def test_parse_annotation_type_in_csv__invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_annotation_type_in_csv("invalid", index=1)
