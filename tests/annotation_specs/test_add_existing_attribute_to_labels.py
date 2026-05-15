from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs.add_existing_attribute_to_labels import (
    build_request_body_for_add_existing_attribute_to_labels,
    resolve_existing_attribute_to_labels_input,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveExistingAttributeToLabelsInput:
    def test_resolve_existing_attribute_to_labels_input__with_attribute_id(self, annotation_specs: dict) -> None:
        actual = resolve_existing_attribute_to_labels_input(
            annotation_specs,
            attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            attribute_name_en=None,
            label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2", "22b5189b-af7b-4d9c-83a5-b92f122170ec"],
            label_name_ens=[],
        )

        assert actual.target_attribute["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
        assert [label["label_id"] for label in actual.target_labels] == [
            "40f7796b-3722-4eed-9c0c-04a27f9165d2",
            "22b5189b-af7b-4d9c-83a5-b92f122170ec",
        ]

    def test_resolve_existing_attribute_to_labels_input__label_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                annotation_specs,
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                label_ids=["not-found"],
                label_name_ens=[],
            )

    def test_resolve_existing_attribute_to_labels_input__attribute_id_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                annotation_specs,
                attribute_id="not-found",
                attribute_name_en=None,
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_resolve_existing_attribute_to_labels_input__attribute_name_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                annotation_specs,
                attribute_id=None,
                attribute_name_en="not-found",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_resolve_existing_attribute_to_labels_input__ambiguous_attribute_name(self, annotation_specs: dict) -> None:
        duplicated_specs = copy.deepcopy(annotation_specs)
        duplicated_attribute = copy.deepcopy(duplicated_specs["additionals"][0])
        duplicated_attribute["additional_data_definition_id"] = "duplicated-id"
        duplicated_specs["additionals"].append(duplicated_attribute)

        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                duplicated_specs,
                attribute_id=None,
                attribute_name_en="comment",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_resolve_existing_attribute_to_labels_input__attribute_id_and_attribute_name_en_are_specified(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                annotation_specs,
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en="comment",
                label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
                label_name_ens=[],
            )

    def test_resolve_existing_attribute_to_labels_input__already_linked_attribute(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_existing_attribute_to_labels_input(
                annotation_specs,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                label_ids=["car_label_id"],
                label_name_ens=[],
            )


class TestBuildRequestBodyForAddExistingAttributeToLabels:
    def test_build_request_body_for_add_existing_attribute_to_labels__with_attribute_id(self, annotation_specs: dict) -> None:
        resolved_input = resolve_existing_attribute_to_labels_input(
            annotation_specs,
            attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            attribute_name_en=None,
            label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2", "22b5189b-af7b-4d9c-83a5-b92f122170ec"],
            label_name_ens=[],
        )

        actual = build_request_body_for_add_existing_attribute_to_labels(
            annotation_specs,
            resolved_input=resolved_input,
            comment=None,
        )

        assert len(actual["additionals"]) == len(annotation_specs["additionals"])
        bike_label = next(label for label in actual["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert bike_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        bus_label = next(label for label in actual["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert bus_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert actual["comment"].startswith("以下の既存属性をラベルに追加しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_add_existing_attribute_to_labels__with_attribute_name(self, annotation_specs: dict) -> None:
        resolved_input = resolve_existing_attribute_to_labels_input(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="comment",
            label_ids=[],
            label_name_ens=["bus"],
        )

        actual = build_request_body_for_add_existing_attribute_to_labels(
            annotation_specs,
            resolved_input=resolved_input,
            comment="custom",
        )

        bus_label = next(label for label in actual["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert bus_label["additional_data_definitions"] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert actual["comment"] == "custom"
