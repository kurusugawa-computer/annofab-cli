from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pandas
import pytest

from annofabcli.annotation_specs import add_labels
from annofabcli.annotation_specs.add_labels import (
    AddLabelsMain,
    LabelInput,
    create_label_color,
    create_label_inputs_from_name_ens,
    read_labels_csv,
    read_labels_json,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)
    add_labels.add_parser(subparsers)
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


class AddLabelsMainWithoutConfirm(AddLabelsMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


class TestAddLabelsMain:
    def test_add_labels(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.add_labels(
            label_inputs=[
                LabelInput(label_id="pedestrian", label_name_en="pedestrian", label_name_ja="歩行者", color="#123456"),
                LabelInput(label_name_en="bicycle"),
            ],
            annotation_type="bounding_box",
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_labels = service.api.last_put["labels"][-2:]
        assert [label["label_id"] for label in added_labels] == ["pedestrian", added_labels[1]["label_id"]]
        assert [label["label_name"]["messages"][0]["message"] for label in added_labels] == ["pedestrian", "bicycle"]
        assert [label["label_name"]["messages"][1]["message"] for label in added_labels] == ["歩行者", "bicycle"]
        assert [label["annotation_type"] for label in added_labels] == ["bounding_box", "bounding_box"]
        assert added_labels[0]["color"] == {"red": 18, "green": 52, "blue": 86}
        assert added_labels[1]["color"] == {"red": 255, "green": 85, "blue": 0}
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_add_labels__invalid_color(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_inputs=[LabelInput(label_name_en="pedestrian", color="red")],
                annotation_type="bounding_box",
            )

    def test_add_labels__duplicated_input(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_inputs=[LabelInput(label_name_en="pedestrian"), LabelInput(label_name_en="pedestrian")],
                annotation_type="bounding_box",
            )

    def test_add_labels__duplicated_input_label_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_inputs=[
                    LabelInput(label_id="pedestrian", label_name_en="pedestrian"),
                    LabelInput(label_id="pedestrian", label_name_en="bicycle"),
                ],
                annotation_type="bounding_box",
            )

    def test_add_labels__duplicated_existing_label_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_inputs=[LabelInput(label_name_en="pedestrian"), LabelInput(label_name_en="car")],
                annotation_type="bounding_box",
            )

    def test_add_labels__empty_label_inputs(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_inputs=[],
                annotation_type="bounding_box",
            )

    def test_add_labels__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.add_labels(
            label_inputs=[LabelInput(label_name_en="pedestrian"), LabelInput(label_name_en="bicycle")],
            annotation_type="bounding_box",
        )

        assert result is False
        assert service.api.last_put is None


class TestReadLabels:
    def test_create_label_inputs_from_name_ens(self) -> None:
        actual = create_label_inputs_from_name_ens(["pedestrian", "bicycle"])

        assert actual == [
            LabelInput(label_name_en="pedestrian"),
            LabelInput(label_name_en="bicycle"),
        ]

    def test_read_labels_json(self) -> None:
        actual = read_labels_json('[{"label_id":"pedestrian","label_name_en":"pedestrian","label_name_ja":"歩行者","color":"#123456"},{"label_name_en":"bicycle"}]')

        assert actual == [
            LabelInput(label_id="pedestrian", label_name_en="pedestrian", label_name_ja="歩行者", color="#123456"),
            LabelInput(label_name_en="bicycle"),
        ]

    def test_read_labels_json__label_name_en_required(self) -> None:
        with pytest.raises(ValueError):
            read_labels_json('[{"label_name_ja":"歩行者"}]')

    def test_read_labels_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "labels.csv"
        df = pandas.DataFrame(
            [
                {"label_id": "pedestrian", "label_name_en": "pedestrian", "label_name_ja": "歩行者", "color": "#123456"},
                {"label_name_en": "bicycle"},
            ]
        )
        df.to_csv(csv_path, index=False)

        actual = read_labels_csv(csv_path)

        assert actual == [
            LabelInput(label_id="pedestrian", label_name_en="pedestrian", label_name_ja="歩行者", color="#123456"),
            LabelInput(label_name_en="bicycle"),
        ]

    def test_read_labels_csv__label_name_en_required(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "labels.csv"
        pandas.DataFrame([{"label_id": "pedestrian", "label_name_ja": "歩行者"}]).to_csv(csv_path, index=False)

        with pytest.raises(ValueError):
            read_labels_csv(csv_path)

    def test_create_label_color(self) -> None:
        actual = create_label_color("#123456", [])

        assert actual == {"red": 18, "green": 52, "blue": 86}
