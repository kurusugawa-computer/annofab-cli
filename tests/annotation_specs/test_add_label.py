from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_label
from annofabcli.annotation_specs.add_label import AddLabelMain, create_auto_color, parse_color

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
    add_label.add_parser(subparsers)
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


class AddLabelMainWithoutConfirm(AddLabelMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


class TestParseArgs:
    def test_parse_args(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "add_label",
                "--project_id",
                "prj1",
                "--label_name_en",
                "pedestrian",
                "--annotation_type",
                "bounding_box",
                "--color",
                "#00CCFF",
            ]
        )
        assert args.label_name_en == "pedestrian"
        assert args.annotation_type == "bounding_box"
        assert args.color == "#00CCFF"

    def test_parse_args__required(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["add_label", "--project_id", "prj1"])

    def test_parse_args__invalid_annotation_type(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "add_label",
                    "--project_id",
                    "prj1",
                    "--label_name_en",
                    "pedestrian",
                    "--annotation_type",
                    "invalid_type",
                ]
            )


class TestColor:
    def test_parse_color(self) -> None:
        actual = parse_color("#00CCFF")
        assert actual == {"red": 0, "green": 204, "blue": 255}

    def test_parse_color__invalid(self) -> None:
        with pytest.raises(ValueError):
            parse_color("00CCFF")

    def test_create_auto_color(self, annotation_specs: dict) -> None:
        actual = create_auto_color(annotation_specs["labels"])
        existing_colors = {(label["color"]["red"], label["color"]["green"], label["color"]["blue"]) for label in annotation_specs["labels"]}
        assert (actual["red"], actual["green"], actual["blue"]) not in existing_colors


class TestAddLabelMain:
    def test_add_label(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.add_label(
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja="歩行者",
            color_code="#00CCFF",
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_label = service.api.last_put["labels"][-1]
        assert added_label["label_id"] == "pedestrian_label_id"
        assert added_label["annotation_type"] == "bounding_box"
        assert added_label["keybind"] == []
        assert added_label["additional_data_definitions"] == []
        assert added_label["color"] == {"red": 0, "green": 204, "blue": 255}
        assert added_label["metadata"] == {}
        assert service.api.last_put["comment"].startswith("以下のラベルを追加しました。")
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_add_label__label_id_is_uuidv4_when_not_specified(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.add_label(
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id=None,
            label_name_ja=None,
            color_code="#00CCFF",
            comment="custom",
        )

        assert service.api.last_put is not None
        generated_label_id = service.api.last_put["labels"][-1]["label_id"]
        assert str(uuid.UUID(generated_label_id, version=4)) == generated_label_id
        assert service.api.last_put["labels"][-1]["label_name"]["messages"][1]["message"] == "pedestrian"
        assert service.api.last_put["comment"] == "custom"

    def test_add_label__auto_color(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.add_label(
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code=None,
            comment=None,
        )

        assert service.api.last_put is not None
        added_color = service.api.last_put["labels"][-1]["color"]
        existing_colors = {(label["color"]["red"], label["color"]["green"], label["color"]["blue"]) for label in annotation_specs["labels"]}
        assert (added_color["red"], added_color["green"], added_color["blue"]) not in existing_colors

    def test_add_label__copy_shape_from_sample_label(self, annotation_specs: dict) -> None:
        shaped_specs = copy.deepcopy(annotation_specs)
        shaped_specs["labels"][0]["field_values"] = {"existing": {"_type": "Dummy"}}
        shaped_specs["labels"][0]["bounding_box_metadata"] = {"value": True}
        shaped_specs["labels"][0]["segmentation_metadata"] = {"value": True}
        shaped_specs["labels"][0]["annotation_editor_feature"] = {"append": True, "erase": True}
        shaped_specs["labels"][0]["allow_out_of_image_bounds"] = True
        service = DummyService(shaped_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.add_label(
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
            comment=None,
        )

        assert service.api.last_put is not None
        added_label = service.api.last_put["labels"][-1]
        assert added_label["field_values"] == {}
        assert added_label["bounding_box_metadata"] is None
        assert added_label["segmentation_metadata"] is None
        assert added_label["annotation_editor_feature"] == {"append": False, "erase": False}
        assert added_label["allow_out_of_image_bounds"] is True

    def test_add_label__duplicated_label_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_label(
                label_name_en="pedestrian",
                annotation_type="bounding_box",
                label_id="car_label_id",
                label_name_ja=None,
                color_code="#00CCFF",
            )

    def test_add_label__duplicated_label_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_label(
                label_name_en="car",
                annotation_type="bounding_box",
                label_id="new_label_id",
                label_name_ja=None,
                color_code="#00CCFF",
            )

    def test_add_label__invalid_color_code(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_label(
                label_name_en="pedestrian",
                annotation_type="bounding_box",
                label_id="pedestrian_label_id",
                label_name_ja=None,
                color_code="00CCFF",
            )

    def test_add_label__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.add_label(
            label_name_en="pedestrian",
            annotation_type="bounding_box",
            label_id="pedestrian_label_id",
            label_name_ja=None,
            color_code="#00CCFF",
        )

        assert result is False
        assert service.api.last_put is None
