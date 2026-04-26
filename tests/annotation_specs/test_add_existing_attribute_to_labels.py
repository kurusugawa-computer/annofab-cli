from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_existing_attribute_to_labels
from annofabcli.annotation_specs.add_existing_attribute_to_labels import AddExistingAttributeToLabelsMain

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
    add_existing_attribute_to_labels.add_parser(subparsers)
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


class TestAddExistingAttributeToLabelsMain:
    def test_add_existing_attribute_to_labels__with_attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_existing_attribute_to_labels(
            attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            attribute_name_en=None,
            label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2", "22b5189b-af7b-4d9c-83a5-b92f122170ec"],
            label_name_ens=[],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        assert len(service.api.last_put["additionals"]) == len(annotation_specs["additionals"])
        bike_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert bike_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        bus_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert bus_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert service.api.last_put["comment"].startswith("以下の既存属性をラベルに追加しました。")
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_add_existing_attribute_to_labels__with_attribute_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        main.add_existing_attribute_to_labels(
            attribute_id=None,
            attribute_name_en="comment",
            label_ids=[],
            label_name_ens=["bus"],
            comment="custom",
        )

        assert service.api.last_put is not None
        bus_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert bus_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert service.api.last_put["comment"] == "custom"

    def test_add_existing_attribute_to_labels__label_not_found(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                label_ids=["not-found"],
                label_name_ens=[],
            )

    def test_add_existing_attribute_to_labels__attribute_id_not_found(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id="not-found",
                attribute_name_en=None,
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_add_existing_attribute_to_labels__attribute_name_not_found(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id=None,
                attribute_name_en="not-found",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_add_existing_attribute_to_labels__ambiguous_attribute_name(self, annotation_specs: dict) -> None:
        duplicated_specs = copy.deepcopy(annotation_specs)
        duplicated_attribute = copy.deepcopy(duplicated_specs["additionals"][0])
        duplicated_attribute["additional_data_definition_id"] = "duplicated-id"
        duplicated_specs["additionals"].append(duplicated_attribute)
        service = DummyService(duplicated_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id=None,
                attribute_name_en="comment",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_add_existing_attribute_to_labels__attribute_id_and_attribute_name_en_are_specified(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en="comment",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_add_existing_attribute_to_labels__already_linked_attribute(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddExistingAttributeToLabelsMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_existing_attribute_to_labels(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                label_ids=["car_label_id"],
                label_name_ens=[],
            )
