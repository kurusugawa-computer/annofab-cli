from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.delete_attribute import (
    build_request_body_for_delete_attribute,
    create_comment_for_delete_attribute,
    create_confirm_message_for_delete_attribute,
    resolve_attribute_deletion,
    restriction_references_attribute,
)

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


def add_same_name_attributes_to_different_labels(annotation_specs: dict[str, Any]) -> None:
    car_foo_attribute = copy.deepcopy(annotation_specs["additionals"][0])
    car_foo_attribute["additional_data_definition_id"] = "car_foo_attribute_id"
    car_foo_attribute["name"]["messages"] = [
        {"lang": "ja-JP", "message": "foo"},
        {"lang": "en-US", "message": "foo"},
    ]
    bus_foo_attribute = copy.deepcopy(car_foo_attribute)
    bus_foo_attribute["additional_data_definition_id"] = "bus_foo_attribute_id"
    annotation_specs["additionals"].extend([car_foo_attribute, bus_foo_attribute])

    car_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "car_label_id")
    bus_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
    car_label["additional_data_definitions"].append("car_foo_attribute_id")
    bus_label["additional_data_definitions"].append("bus_foo_attribute_id")


def add_same_name_attributes_to_same_label(annotation_specs: dict[str, Any]) -> None:
    foo_attribute_1 = copy.deepcopy(annotation_specs["additionals"][0])
    foo_attribute_1["additional_data_definition_id"] = "car_foo_attribute_id_1"
    foo_attribute_1["name"]["messages"] = [
        {"lang": "ja-JP", "message": "foo"},
        {"lang": "en-US", "message": "foo"},
    ]
    foo_attribute_2 = copy.deepcopy(foo_attribute_1)
    foo_attribute_2["additional_data_definition_id"] = "car_foo_attribute_id_2"
    annotation_specs["additionals"].extend([foo_attribute_1, foo_attribute_2])

    car_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "car_label_id")
    car_label["additional_data_definitions"].extend(["car_foo_attribute_id_1", "car_foo_attribute_id_2"])


class TestDeleteAttributeHelpers:
    def test_restriction_references_attribute__ネストされた属性参照を検出する(self) -> None:
        annotation_specs = load_annotation_specs()
        restriction = annotation_specs["restrictions"][-1]

        assert restriction_references_attribute(restriction, {"f12a0b59-dfce-4241-bb87-4b2c0259fc6f"}) is True
        assert restriction_references_attribute(restriction, {"not-found"}) is False

    def test_create_comment_for_delete_attribute(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = create_comment_for_delete_attribute(resolved)

        assert "以下のラベルから属性を削除しました。" in actual
        assert "label_name_en='car', attribute_name_en='unclear'" in actual
        assert "'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'" in actual

    def test_create_confirm_message_for_delete_attribute(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = create_confirm_message_for_delete_attribute(resolved, affecting_annotations=[])

        assert "以下のラベルから属性(1件)を削除します。" in actual
        assert "label_name_en='car', attribute_name_en='unclear'" in actual
        assert "属性定義" not in actual
        assert actual.endswith("よろしいですか？")


class TestResolveAttributeDeletion:
    def test_resolve_attribute_deletion__同じラベル内で属性名が重複しているときはエラー(self) -> None:
        annotation_specs = load_annotation_specs()
        add_same_name_attributes_to_same_label(annotation_specs)

        with pytest.raises(ValueError):
            resolve_attribute_deletion(
                annotation_specs,
                attribute_ids=None,
                attribute_name_ens=["foo"],
                label_ids=None,
                label_name_ens=["car"],
            )

    def test_resolve_attribute_deletion__属性名が重複していてもラベルで絞り込める(self) -> None:
        annotation_specs = load_annotation_specs()
        add_same_name_attributes_to_different_labels(annotation_specs)

        actual = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["foo"],
            label_ids=None,
            label_name_ens=["bus"],
        )

        assert [(pair.label["label_id"], pair.attribute["additional_data_definition_id"]) for pair in actual.label_attribute_pairs] == [
            ("22b5189b-af7b-4d9c-83a5-b92f122170ec", "bus_foo_attribute_id")
        ]

    def test_resolve_attribute_deletion__all_labelsは同じ属性名の属性をすべて対象にする(self) -> None:
        annotation_specs = load_annotation_specs()
        add_same_name_attributes_to_different_labels(annotation_specs)

        actual = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["foo"],
            label_ids=None,
            label_name_ens=None,
            all_labels=True,
        )

        assert [(pair.label["label_id"], pair.attribute["additional_data_definition_id"]) for pair in actual.label_attribute_pairs] == [
            ("car_label_id", "car_foo_attribute_id"),
            ("22b5189b-af7b-4d9c-83a5-b92f122170ec", "bus_foo_attribute_id"),
        ]

    def test_resolve_attribute_deletion__指定ラベルから属性を削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        bus_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        bus_label["additional_data_definitions"].append("54fa5e97-6f88-49a4-aeb0-a91a15d11528")

        actual = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["comment"],
            label_ids=None,
            label_name_ens=["car"],
        )

        assert [(pair.label["label_id"], pair.attribute["additional_data_definition_id"]) for pair in actual.label_attribute_pairs] == [("car_label_id", "54fa5e97-6f88-49a4-aeb0-a91a15d11528")]
        assert actual.orphan_attributes == []
        assert actual.restrictions_to_remove == []

    def test_resolve_attribute_deletion__all_labelsは属性が紐づくすべてのラベルを対象にする(self) -> None:
        annotation_specs = load_annotation_specs()
        bus_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        bus_label["additional_data_definitions"].append("54fa5e97-6f88-49a4-aeb0-a91a15d11528")

        actual = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["comment"],
            label_ids=None,
            label_name_ens=None,
            all_labels=True,
        )

        assert [(pair.label["label_id"], pair.attribute["additional_data_definition_id"]) for pair in actual.label_attribute_pairs] == [
            ("car_label_id", "54fa5e97-6f88-49a4-aeb0-a91a15d11528"),
            ("22b5189b-af7b-4d9c-83a5-b92f122170ec", "54fa5e97-6f88-49a4-aeb0-a91a15d11528"),
        ]
        assert [attribute["additional_data_definition_id"] for attribute in actual.orphan_attributes] == ["54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert len(actual.restrictions_to_remove) == 7

    def test_resolve_attribute_deletion__ラベルに属性が紐づいていないときはエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_attribute_deletion(
                annotation_specs,
                attribute_ids=None,
                attribute_name_ens=["comment"],
                label_ids=None,
                label_name_ens=["bike"],
            )

    def test_resolve_attribute_deletion__孤立属性を参照する属性制約も削除対象にする(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            label_ids=None,
            label_name_ens=["car"],
        )

        assert [attribute["additional_data_definition_id"] for attribute in actual.orphan_attributes] == ["f12a0b59-dfce-4241-bb87-4b2c0259fc6f"]
        assert actual.restriction_text_list == ["'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'"]


class TestBuildRequestBodyForDeleteAttribute:
    def test_build_request_body_for_delete_attribute__孤立属性と関連制約も削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = build_request_body_for_delete_attribute(annotation_specs, resolved_deletion=resolved, comment=None)

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert "f12a0b59-dfce-4241-bb87-4b2c0259fc6f" not in car_label["additional_data_definitions"]
        assert all(attribute["additional_data_definition_id"] != "f12a0b59-dfce-4241-bb87-4b2c0259fc6f" for attribute in actual["additionals"])
        assert all(not restriction_references_attribute(restriction, {"f12a0b59-dfce-4241-bb87-4b2c0259fc6f"}) for restriction in actual["restrictions"])
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下のラベルから属性を削除しました。" in actual["comment"]

    def test_build_request_body_for_delete_attribute__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_deletion(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = build_request_body_for_delete_attribute(annotation_specs, resolved_deletion=resolved, comment="custom")

        assert actual["comment"] == "custom"
