from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.delete_labels import (
    AffectingAnnotation,
    DeleteLabelsMain,
    build_request_body_for_delete_labels,
    create_comment_for_delete_labels,
    create_confirm_message_for_delete_labels,
    resolve_label_deletion,
    restriction_references_label,
)

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


def share_car_attribute_with_bus(annotation_specs: dict[str, Any], attribute_id: str) -> None:
    bus_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "22b5189b-af7b-4d9c-83a5-b92f122170ec")
    bus_label["additional_data_definitions"].append(attribute_id)


class TestDeleteLabelsHelpers:
    def test_restriction_references_label__has_labelを検出する(self) -> None:
        annotation_specs = load_annotation_specs()
        restriction = annotation_specs["restrictions"][-2]

        assert restriction_references_label(restriction, {"40f7796b-3722-4eed-9c0c-04a27f9165d2"}) is True
        assert restriction_references_label(restriction, {"car_label_id"}) is False

    def test_create_comment_for_delete_labels(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bike"],
        )

        actual = create_comment_for_delete_labels(resolved)

        assert "以下のラベルを削除しました。" in actual
        assert "label_name_en='bike'" in actual
        assert "'link' HAS LABEL 'bike', 'bus'" in actual

    def test_create_confirm_message_for_delete_labels(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bike"],
        )

        actual = create_confirm_message_for_delete_labels(resolved, affecting_annotations=[])

        assert "以下のラベル(1件)を削除します。" in actual
        assert "label_name_en='bike'" in actual
        assert "以下の属性も" not in actual
        assert actual.endswith("よろしいですか？")


class TestResolveLabelDeletion:
    def test_resolve_label_deletion__指定ラベルを削除対象にする(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bike"],
        )

        assert [label["label_id"] for label in actual.labels_to_remove] == ["40f7796b-3722-4eed-9c0c-04a27f9165d2"]
        assert actual.orphan_attributes == []
        assert actual.restriction_text_list == ["'link' HAS LABEL 'bike', 'bus'"]

    def test_resolve_label_deletion__削除ラベルだけが参照する属性を孤立属性にする(self) -> None:
        annotation_specs = load_annotation_specs()
        share_car_attribute_with_bus(annotation_specs, "54fa5e97-6f88-49a4-aeb0-a91a15d11528")

        actual = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["car"],
        )

        assert [attribute["additional_data_definition_id"] for attribute in actual.orphan_attributes] == [
            "15235360-4f46-42ac-927d-0e046bf52ddd",
            "71620647-98cf-48ad-b43b-4af425a24f32",
            "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
        ]
        assert "'comment' CAN NOT INPUT" not in actual.restriction_text_list
        assert "'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'" in actual.restriction_text_list

    def test_resolve_label_deletion__id指定で対象を解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_label_deletion(
            annotation_specs,
            label_ids=["22b5189b-af7b-4d9c-83a5-b92f122170ec"],
            label_name_ens=None,
        )

        assert [label["label_id"] for label in actual.labels_to_remove] == ["22b5189b-af7b-4d9c-83a5-b92f122170ec"]
        assert actual.restriction_text_list == ["'link' HAS LABEL 'bike', 'bus'"]


class TestBuildRequestBodyForDeleteLabels:
    def test_build_request_body_for_delete_labels__孤立属性と関連制約も削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = build_request_body_for_delete_labels(annotation_specs, resolved_deletion=resolved, comment=None)

        assert all(label["label_id"] != "car_label_id" for label in actual["labels"])
        assert actual["additionals"] == []
        assert actual["restrictions"] == []
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下のラベルを削除しました。" in actual["comment"]

    def test_build_request_body_for_delete_labels__共有属性は削除しない(self) -> None:
        annotation_specs = load_annotation_specs()
        share_car_attribute_with_bus(annotation_specs, "54fa5e97-6f88-49a4-aeb0-a91a15d11528")
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["car"],
        )

        actual = build_request_body_for_delete_labels(annotation_specs, resolved_deletion=resolved, comment=None)

        assert any(attribute["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528" for attribute in actual["additionals"])

    def test_build_request_body_for_delete_labels__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bike"],
        )

        actual = build_request_body_for_delete_labels(annotation_specs, resolved_deletion=resolved, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_delete_labels__元のアノテーション仕様は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved = resolve_label_deletion(
            annotation_specs,
            label_ids=None,
            label_name_ens=["bike"],
        )

        build_request_body_for_delete_labels(annotation_specs, resolved_deletion=resolved, comment=None)

        assert annotation_specs == old_annotation_specs


class TestDeleteLabelsMain:
    def test_validate_deletion__既存アノテーションに影響するときは許可オプションを案内する(self, caplog: pytest.LogCaptureFixture) -> None:
        obj = DeleteLabelsMain(
            service=None,  # type: ignore[arg-type]
            project_id="project_id",
            all_yes=True,
            allow_affecting_annotations=False,
        )

        with caplog.at_level(logging.WARNING):
            actual = obj.validate_deletion(
                [
                    AffectingAnnotation(
                        label_name_en="car",
                        annotation_count=3,
                    )
                ]
            )

        assert actual is False
        assert "--allow_affecting_annotations" in caplog.text
