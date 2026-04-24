from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_labels
from annofabcli.annotation_specs.add_labels import AddLabelsMain

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


class TestParseArgs:
    def test_parse_args(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "add_labels",
                "--project_id",
                "prj1",
                "--label_name_en",
                "pedestrian",
                "bicycle",
                "--annotation_type",
                "bounding_box",
            ]
        )
        assert args.label_name_en == ["pedestrian", "bicycle"]
        assert args.annotation_type == "bounding_box"

    def test_parse_args__required(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["add_labels", "--project_id", "prj1"])

    def test_parse_args__invalid_annotation_type(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "add_labels",
                    "--project_id",
                    "prj1",
                    "--label_name_en",
                    "pedestrian",
                    "bicycle",
                    "--annotation_type",
                    "invalid_type",
                ]
            )


class TestAddLabelsMain:
    def test_add_labels(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.add_labels(
            label_name_ens=["pedestrian", "bicycle"],
            annotation_type="bounding_box",
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_labels = service.api.last_put["labels"][-2:]
        assert [label["label_name"]["messages"][0]["message"] for label in added_labels] == ["pedestrian", "bicycle"]
        assert [label["annotation_type"] for label in added_labels] == ["bounding_box", "bounding_box"]
        assert added_labels[0]["color"] == {"red": 255, "green": 85, "blue": 0}
        assert added_labels[1]["color"] == {"red": 255, "green": 170, "blue": 0}
        assert service.api.last_put["comment"] == "以下のラベルを追加しました。\nラベル名(英語): pedestrian, bicycle\nannotation_type: bounding_box"
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_add_labels__duplicated_input(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_name_ens=["pedestrian", "pedestrian"],
                annotation_type="bounding_box",
            )

    def test_add_labels__duplicated_existing_label_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_name_ens=["pedestrian", "car"],
                annotation_type="bounding_box",
            )

    def test_add_labels__empty_label_names(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.add_labels(
                label_name_ens=[],
                annotation_type="bounding_box",
            )

    def test_add_labels__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddLabelsMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.add_labels(
            label_name_ens=["pedestrian", "bicycle"],
            annotation_type="bounding_box",
        )

        assert result is False
        assert service.api.last_put is None
