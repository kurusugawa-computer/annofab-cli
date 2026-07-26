from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.reorder_labels import (
    build_request_body_for_reorder_labels,
    create_comment_for_reorder_labels,
    create_confirm_message_for_reorder_labels,
    resolve_label_reorder,
    validate_label_reorder_inputs,
)

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveLabelReorder:
    def test_resolve_label_reorder__name指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus", "car"],
        )

        assert [label["label_id"] for label in actual.first_labels] == ["22b5189b-af7b-4d9c-83a5-b92f122170ec", "car_label_id"]

    def test_resolve_label_reorder__id指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_label_reorder(
            annotation_specs,
            label_ids=["22b5189b-af7b-4d9c-83a5-b92f122170ec", "car_label_id"],
            label_name_ens=None,
        )

        assert [label["label_id"] for label in actual.first_labels] == ["22b5189b-af7b-4d9c-83a5-b92f122170ec", "car_label_id"]

    def test_resolve_label_reorder__存在しないラベルならエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_label_reorder(
                annotation_specs,
                label_ids=None,
                label_name_ens=["not-found"],
            )


class TestValidateLabelReorderInputs:
    def test_validate_label_reorder_inputs__idとnameを同時指定したらエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_label_reorder_inputs(label_ids=["car_label_id"], label_name_ens=["car"])

    def test_validate_label_reorder_inputs__指定なしならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_label_reorder_inputs(label_ids=[], label_name_ens=None)

    def test_validate_label_reorder_inputs__重複したidならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_label_reorder_inputs(label_ids=["car_label_id", "car_label_id"], label_name_ens=None)

    def test_validate_label_reorder_inputs__重複したnameならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_label_reorder_inputs(label_ids=None, label_name_ens=["car", "car"])


class TestMessage:
    def test_create_comment_for_reorder_labels(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus", "car"],
        )

        actual = create_comment_for_reorder_labels(resolved)

        assert "以下のラベルを指定順で先頭に移動しました。" in actual
        assert "対象ラベル: bus, car" in actual

    def test_create_confirm_message_for_reorder_labels(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus", "car"],
        )

        actual = create_confirm_message_for_reorder_labels(resolved)

        assert "以下のラベル(2件)を指定順で先頭に移動します。" in actual
        assert "指定しなかったラベルは現在の順番を維持します。" in actual
        assert actual.endswith("よろしいですか？")


class TestBuildRequestBodyForReorderLabels:
    def test_build_request_body_for_reorder_labels__指定ラベルを先頭に移動する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus", "car"],
        )

        actual = build_request_body_for_reorder_labels(annotation_specs, resolved_reorder=resolved, comment=None)

        assert [label["label_id"] for label in actual["labels"]] == [
            "22b5189b-af7b-4d9c-83a5-b92f122170ec",
            "car_label_id",
            "40f7796b-3722-4eed-9c0c-04a27f9165d2",
        ]
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下のラベルを指定順で先頭に移動しました。" in actual["comment"]

    def test_build_request_body_for_reorder_labels__未指定ラベルの順番を維持する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=["40f7796b-3722-4eed-9c0c-04a27f9165d2"],
            label_name_ens=None,
        )

        actual = build_request_body_for_reorder_labels(annotation_specs, resolved_reorder=resolved, comment=None)

        assert [label["label_id"] for label in actual["labels"]] == [
            "40f7796b-3722-4eed-9c0c-04a27f9165d2",
            "car_label_id",
            "22b5189b-af7b-4d9c-83a5-b92f122170ec",
        ]

    def test_build_request_body_for_reorder_labels__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus"],
        )

        actual = build_request_body_for_reorder_labels(annotation_specs, resolved_reorder=resolved, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_reorder_labels__元のアノテーション仕様は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved = resolve_label_reorder(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bus"],
        )

        build_request_body_for_reorder_labels(annotation_specs, resolved_reorder=resolved, comment=None)

        assert annotation_specs == old_annotation_specs
