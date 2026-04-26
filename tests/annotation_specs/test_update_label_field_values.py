from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import update_label_field_values
from annofabcli.annotation_specs.update_label_field_values import UpdateLabelFieldValuesMain

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)
    update_label_field_values.add_parser(subparsers)
    return parser


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


class UpdateLabelFieldValuesMainWithoutConfirm(UpdateLabelFieldValuesMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


class TestUpdateLabelFieldValuesMain:
    def test_update_label_field_values__merge(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.update_label_field_values(
            label_ids=[],
            label_name_ens=["car", "bike"],
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

        assert result is True
        assert service.api.last_put is not None
        car_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "car_label_id")
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
        bike_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert bike_label["field_values"] == {
            "minimum_size_2d_with_default_insert_position": {
                "_type": "MinimumSize2dWithDefaultInsertPosition",
                "min_warn_rule": {"_type": "And"},
                "min_width": 16,
                "min_height": 8,
                "position_for_minimum_bounding_box_insertion": None,
            }
        }
        assert "field_values を更新しました" in service.api.last_put["comment"]
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_update_label_field_values__replace(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.update_label_field_values(
            label_ids=["car_label_id"],
            label_name_ens=[],
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

        assert service.api.last_put is not None
        car_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {
            "display_line_direction": {
                "_type": "DisplayLineDirection",
                "value": True,
            }
        }
        assert service.api.last_put["comment"] == "custom"

    def test_update_label_field_values__clear(self, annotation_specs: dict) -> None:
        annotation_specs["labels"][0]["field_values"] = {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.update_label_field_values(
            label_ids=[],
            label_name_ens=["car"],
            field_values=None,
            replace=False,
            clear=True,
            comment=None,
        )

        assert service.api.last_put is not None
        car_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "car_label_id")
        assert car_label["field_values"] == {}
        assert "field_values をクリアしました" in service.api.last_put["comment"]

    def test_update_label_field_values__replace_and_clear_are_specified(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.update_label_field_values(
                label_ids=[],
                label_name_ens=["car"],
                field_values=None,
                replace=True,
                clear=True,
            )

    def test_update_label_field_values__label_not_found(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.update_label_field_values(
                label_ids=["not-found"],
                label_name_ens=[],
                field_values={},
                replace=False,
                clear=False,
            )

    def test_update_label_field_values__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = UpdateLabelFieldValuesMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.update_label_field_values(
            label_ids=[],
            label_name_ens=["car"],
            field_values={
                "display_line_direction": {
                    "_type": "DisplayLineDirection",
                    "value": True,
                }
            },
            replace=False,
            clear=False,
        )

        assert result is False
        assert service.api.last_put is None


class TestValidateFieldValuesInput:
    def test_field_values_json_is_not_object(self) -> None:
        with pytest.raises(TypeError):
            update_label_field_values.validate_field_values_input([{"_type": "Dummy"}])
