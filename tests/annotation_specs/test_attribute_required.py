from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs.attribute_required import (
    REQUIRED_CONDITION,
    AttributeRequiredMain,
    create_required_restriction,
    is_required_restriction,
)

data_dir = Path("./tests/data/annotation_specs")


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


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


class TestIsRequiredRestriction:
    def test_true(self) -> None:
        assert is_required_restriction(create_required_restriction("attr1")) is True

    def test_false_when_attribute_id_is_different(self) -> None:
        assert is_required_restriction(create_required_restriction("attr1"), attribute_id="attr2") is False

    def test_false_when_condition_is_different(self) -> None:
        restriction = {"additional_data_definition_id": "attr1", "condition": {"value": "foo", "_type": "NotEquals"}}
        assert is_required_restriction(restriction) is False


class TestAttributeRequiredMain:
    def test_set_attribute_required__attribute_name_en(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AttributeRequiredMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.set_attribute_required(
            attribute_ids=None,
            attribute_name_ens=["type", "link"],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_restrictions = [restriction for restriction in service.api.last_put["restrictions"] if restriction["condition"] == REQUIRED_CONDITION]
        added_attribute_ids = {restriction["additional_data_definition_id"] for restriction in added_restrictions}
        assert {"71620647-98cf-48ad-b43b-4af425a24f32", "15235360-4f46-42ac-927d-0e046bf52ddd"} <= added_attribute_ids
        assert service.api.last_put["comment"] == "以下の属性を必須にしました。\ntype\nlink"

    def test_set_attribute_required__already_required_is_skipped(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AttributeRequiredMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.set_attribute_required(
            attribute_ids=["54fa5e97-6f88-49a4-aeb0-a91a15d11528", "15235360-4f46-42ac-927d-0e046bf52ddd"],
            attribute_name_ens=None,
            comment="custom",
        )

        assert result is True
        assert service.api.last_put is not None
        added_restrictions = [restriction for restriction in service.api.last_put["restrictions"] if restriction["condition"] == REQUIRED_CONDITION]
        added_attribute_ids = [restriction["additional_data_definition_id"] for restriction in added_restrictions]
        assert added_attribute_ids.count("54fa5e97-6f88-49a4-aeb0-a91a15d11528") == 1
        assert added_attribute_ids.count("15235360-4f46-42ac-927d-0e046bf52ddd") == 1
        assert service.api.last_put["comment"] == "custom"

    def test_unset_attribute_required__attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AttributeRequiredMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.unset_attribute_required(
            attribute_ids=["54fa5e97-6f88-49a4-aeb0-a91a15d11528"],
            attribute_name_ens=None,
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        remaining_required_restrictions = [
            restriction
            for restriction in service.api.last_put["restrictions"]
            if restriction["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528" and restriction["condition"] == REQUIRED_CONDITION
        ]
        assert remaining_required_restrictions == []
        assert service.api.last_put["comment"] == "以下の属性の必須制約を解除しました。\ncomment"

    def test_unset_attribute_required__attribute_not_required(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AttributeRequiredMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.unset_attribute_required(
            attribute_ids=None,
            attribute_name_ens=["link"],
            comment=None,
        )

        assert result is False
        assert service.api.last_put is None
