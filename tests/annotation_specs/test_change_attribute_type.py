from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import change_attribute_type
from annofabcli.annotation_specs.change_attribute_type import (
    build_request_body_for_change_attribute_type,
    resolve_attribute_type_change,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestCreateConfirmMessageForChangeAttributeType:
    def test_used_label(self) -> None:
        actual = change_attribute_type.create_confirm_message_for_change_attribute_type(
            attribute_name_en="type",
            attribute_id="attr1",
            current_type="select",
            target_type="choice",
            has_annotation_with_label_having_attribute=True,
        )

        assert "この属性を含むラベルがアノテーションで使われています。" in actual
        assert "3次元エディタでは属性値が消えてしまう恐れがあります。" in actual

    def test_unused_label(self) -> None:
        actual = change_attribute_type.create_confirm_message_for_change_attribute_type(
            attribute_name_en="type",
            attribute_id="attr1",
            current_type="select",
            target_type="choice",
            has_annotation_with_label_having_attribute=False,
        )

        assert "この属性を含むラベルがアノテーションで使われていることは確認できませんでした。" in actual
        assert "3次元エディタでは属性値が消えてしまう恐れがあります。" not in actual


class TestValidateAttributeTypeConversion:
    def test_validate_attribute_type_conversion__unsupported(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="flag", target_type="text")

    def test_validate_attribute_type_conversion__same_type(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="text", target_type="text")


class TestResolveAttributeTypeChange:
    def test_resolve_attribute_type_change(self, annotation_specs: dict) -> None:
        actual = resolve_attribute_type_change(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            attribute_type="choice",
        )

        assert actual.target_attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"
        assert actual.current_type == "select"


class TestBuildRequestBodyForChangeAttributeType:
    def test_build_request_body_for_change_attribute_type(self, annotation_specs: dict) -> None:
        resolved_change = resolve_attribute_type_change(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            attribute_type="choice",
        )

        actual = build_request_body_for_change_attribute_type(
            annotation_specs,
            resolved_change=resolved_change,
            attribute_type="choice",
            comment=None,
        )

        changed_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert changed_attribute["type"] == "choice"
        assert actual["comment"] == "以下の属性の種類を変更しました。\n属性名(英語): type\n変更前: select\n変更後: choice"
