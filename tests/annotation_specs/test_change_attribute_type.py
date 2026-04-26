from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import change_attribute_type
from annofabcli.annotation_specs.change_attribute_type import ChangeAttributeTypeMain

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
    change_attribute_type.add_parser(subparsers)
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


class ChangeAttributeTypeMainWithoutConfirm(ChangeAttributeTypeMain):
    def confirm_processing(self, _confirm_message: str) -> bool:
        return False


class TestChangeAttributeTypeMain:
    def test_change_attribute_type__select_to_choice(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = ChangeAttributeTypeMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.change_attribute_type(
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            attribute_type="choice",
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        changed_attribute = next(additional for additional in service.api.last_put["additionals"] if additional["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert changed_attribute["type"] == "choice"
        assert changed_attribute["choices"] == annotation_specs["additionals"][2]["choices"]
        assert changed_attribute["default"] == annotation_specs["additionals"][2]["default"]
        assert "属性の種類を変更しました" in service.api.last_put["comment"]
        assert service.api.last_put["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_change_attribute_type__comment_to_text(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = ChangeAttributeTypeMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        main.change_attribute_type(
            attribute_id=None,
            attribute_name_en="comment",
            attribute_type="text",
            comment="custom",
        )

        assert service.api.last_put is not None
        changed_attribute = next(additional for additional in service.api.last_put["additionals"] if additional["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528")
        assert changed_attribute["type"] == "text"
        assert changed_attribute["default"] == annotation_specs["additionals"][0]["default"]
        assert changed_attribute["choices"] == annotation_specs["additionals"][0]["choices"]
        assert service.api.last_put["comment"] == "custom"

    def test_change_attribute_type__same_type(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = ChangeAttributeTypeMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.change_attribute_type(
                attribute_id=None,
                attribute_name_en="comment",
                attribute_type="comment",
            )

    def test_change_attribute_type__unsupported_conversion(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = ChangeAttributeTypeMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            main.change_attribute_type(
                attribute_id=None,
                attribute_name_en="comment",
                attribute_type="choice",
            )

    def test_change_attribute_type__confirm_no(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = ChangeAttributeTypeMainWithoutConfirm(service, project_id="prj1", all_yes=False)  # type: ignore[arg-type]

        result = main.change_attribute_type(
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            attribute_type="choice",
        )

        assert result is False
        assert service.api.last_put is None


class TestValidateAttributeTypeConversion:
    def test_validate_attribute_type_conversion__unsupported(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="flag", target_type="text")

    def test_validate_attribute_type_conversion__same_type(self) -> None:
        with pytest.raises(ValueError):
            change_attribute_type.validate_attribute_type_conversion(current_type="text", target_type="text")
