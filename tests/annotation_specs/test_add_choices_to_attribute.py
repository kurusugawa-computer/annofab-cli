from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_choices_to_attribute
from annofabcli.annotation_specs.add_choices_to_attribute import AddChoicesToAttributeMain

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
    add_choices_to_attribute.add_parser(subparsers)
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


class TestAddChoicesToAttributeMain:
    def test_add_choices_to_attribute__attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_choices_to_attribute(
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_json='[{"choice_id":"xlarge","choice_name_en":"xlarge","choice_name_ja":"特大"},{"choice_id":"tiny","choice_name_en":"tiny","choice_name_ja":"極小"}]',
            choice_csv=None,
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        updated_attribute = next(attribute for attribute in service.api.last_put["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert [choice["choice_id"] for choice in updated_attribute["choices"][-2:]] == ["xlarge", "tiny"]
        assert updated_attribute["default"] == ""
        assert service.api.last_put["comment"].startswith("以下の選択肢を属性に追加しました。")

    def test_add_choices_to_attribute__attribute_name_and_ignore_default(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_choices_to_attribute(
            attribute_id=None,
            attribute_name_en="type",
            choice_json='[{"choice_id":"xlarge","choice_name_en":"xlarge","is_default":true}]',
            choice_csv=None,
            comment="custom",
        )

        assert result is True
        assert service.api.last_put is not None
        updated_attribute = next(attribute for attribute in service.api.last_put["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert updated_attribute["default"] == ""
        assert service.api.last_put["comment"] == "custom"

    def test_add_choices_to_attribute__ignore_default_in_csv(self, annotation_specs: dict, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text("choice_id,choice_name_en,is_default\nxlarge,xlarge,true\n", encoding="utf-8")
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_choices_to_attribute(
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_json=None,
            choice_csv=csv_path,
        )

        assert result is True
        assert service.api.last_put is not None
        updated_attribute = next(attribute for attribute in service.api.last_put["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert updated_attribute["default"] == ""

    def test_add_choices_to_attribute__duplicated_existing_choice_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_choices_to_attribute(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_json='[{"choice_id":"08ec927c-18e6-4bba-837a-b16de7061580","choice_name_en":"xlarge"}]',
                choice_csv=None,
            )

    def test_add_choices_to_attribute__duplicated_existing_choice_name_en(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_choices_to_attribute(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_json='[{"choice_id":"xlarge","choice_name_en":"large"}]',
                choice_csv=None,
            )

    def test_add_choices_to_attribute__attribute_not_choice(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_choices_to_attribute(
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                choice_json='[{"choice_id":"xlarge","choice_name_en":"xlarge"}]',
                choice_csv=None,
            )

    def test_add_choices_to_attribute__ignore_default_when_default_already_exists(self, annotation_specs: dict) -> None:
        duplicated_specs = copy.deepcopy(annotation_specs)
        target_attribute = next(attribute for attribute in duplicated_specs["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        target_attribute["default"] = "08ec927c-18e6-4bba-837a-b16de7061580"
        service = DummyService(duplicated_specs)
        main = AddChoicesToAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_choices_to_attribute(
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_json='[{"choice_id":"xlarge","choice_name_en":"xlarge","is_default":true}]',
            choice_csv=None,
        )

        assert result is True
        assert service.api.last_put is not None
        updated_attribute = next(attribute for attribute in service.api.last_put["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert updated_attribute["default"] == "08ec927c-18e6-4bba-837a-b16de7061580"
