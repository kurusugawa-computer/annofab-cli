from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.reorder_attributes import (
    build_request_body_for_reorder_attributes,
    create_comment_for_reorder_attributes,
    create_confirm_message_for_reorder_attributes,
    get_target_attribute_by_id_and_label,
    resolve_attribute_reorder,
    validate_attribute_reorder_inputs,
)

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveAttributeReorder:
    def test_resolve_attribute_reorder__name指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["unclear", "link"],
        )

        assert actual.target_label["label_id"] == "car_label_id"
        assert [attribute["additional_data_definition_id"] for attribute in actual.first_attributes] == [
            "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
            "15235360-4f46-42ac-927d-0e046bf52ddd",
        ]

    def test_resolve_attribute_reorder__id指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_attribute_reorder(
            annotation_specs,
            label_id="car_label_id",
            label_name_en=None,
            attribute_ids=[
                "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
                "15235360-4f46-42ac-927d-0e046bf52ddd",
            ],
            attribute_name_ens=None,
        )

        assert actual.target_label["label_id"] == "car_label_id"
        assert [attribute["additional_data_definition_id"] for attribute in actual.first_attributes] == [
            "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
            "15235360-4f46-42ac-927d-0e046bf52ddd",
        ]

    def test_resolve_attribute_reorder__対象ラベルにない属性ならエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_attribute_reorder(
                annotation_specs,
                label_id=None,
                label_name_en="bike",
                attribute_ids=None,
                attribute_name_ens=["comment"],
            )


class TestGetTargetAttributeByIdAndLabel:
    def test_get_target_attribute_by_id_and_label__対象ラベルに紐づかない属性ならエラー(self) -> None:
        annotation_specs = load_annotation_specs()
        bike_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")

        with pytest.raises(ValueError):
            get_target_attribute_by_id_and_label(
                annotation_specs,
                attribute_id="f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
                label=bike_label,
            )


class TestValidateAttributeReorderInputs:
    def test_validate_attribute_reorder_inputs__labelのidとnameを同時指定したらエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_reorder_inputs(
                label_id="car_label_id",
                label_name_en="car",
                attribute_ids=["f12a0b59-dfce-4241-bb87-4b2c0259fc6f"],
                attribute_name_ens=None,
            )

    def test_validate_attribute_reorder_inputs__attributeのidとnameを同時指定したらエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_reorder_inputs(
                label_id="car_label_id",
                label_name_en=None,
                attribute_ids=["f12a0b59-dfce-4241-bb87-4b2c0259fc6f"],
                attribute_name_ens=["comment"],
            )

    def test_validate_attribute_reorder_inputs__属性指定なしならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_reorder_inputs(
                label_id="car_label_id",
                label_name_en=None,
                attribute_ids=[],
                attribute_name_ens=None,
            )

    def test_validate_attribute_reorder_inputs__重複したidならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_reorder_inputs(
                label_id="car_label_id",
                label_name_en=None,
                attribute_ids=["f12a0b59-dfce-4241-bb87-4b2c0259fc6f", "f12a0b59-dfce-4241-bb87-4b2c0259fc6f"],
                attribute_name_ens=None,
            )

    def test_validate_attribute_reorder_inputs__重複したnameならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_reorder_inputs(
                label_id="car_label_id",
                label_name_en=None,
                attribute_ids=None,
                attribute_name_ens=["comment", "comment"],
            )


class TestMessage:
    def test_create_comment_for_reorder_attributes(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["unclear", "link"],
        )

        actual = create_comment_for_reorder_attributes(resolved)

        assert "以下のラベルの属性を指定順で先頭に移動しました。" in actual
        assert "対象ラベル: car" in actual
        assert "対象属性: unclear, link" in actual

    def test_create_confirm_message_for_reorder_attributes(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["unclear", "link"],
        )

        actual = create_confirm_message_for_reorder_attributes(resolved)

        assert "ラベル 'car' の属性(2件)を指定順で先頭に移動します。" in actual
        assert "指定しなかった属性は現在の順番を維持します。" in actual
        assert actual.endswith("よろしいですか？")


class TestBuildRequestBodyForReorderAttributes:
    def test_build_request_body_for_reorder_attributes__指定属性を対象ラベル内の先頭に移動する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["unclear", "link"],
        )

        actual = build_request_body_for_reorder_attributes(annotation_specs, resolved_reorder=resolved, comment=None)

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["additional_data_definitions"] == [
            "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
            "15235360-4f46-42ac-927d-0e046bf52ddd",
            "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "71620647-98cf-48ad-b43b-4af425a24f32",
        ]
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下のラベルの属性を指定順で先頭に移動しました。" in actual["comment"]

    def test_build_request_body_for_reorder_attributes__対象外ラベルは変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        bus_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        bus_label["additional_data_definitions"] = ["f12a0b59-dfce-4241-bb87-4b2c0259fc6f"]
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        actual = build_request_body_for_reorder_attributes(annotation_specs, resolved_reorder=resolved, comment=None)

        actual_bus_label = next(label for label in actual["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
        assert actual_bus_label["additional_data_definitions"] == ["f12a0b59-dfce-4241-bb87-4b2c0259fc6f"]

    def test_build_request_body_for_reorder_attributes__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        actual = build_request_body_for_reorder_attributes(annotation_specs, resolved_reorder=resolved, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_reorder_attributes__元のアノテーション仕様は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved = resolve_attribute_reorder(
            annotation_specs,
            label_id=None,
            label_name_en="car",
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        build_request_body_for_reorder_attributes(annotation_specs, resolved_reorder=resolved, comment=None)

        assert annotation_specs == old_annotation_specs
