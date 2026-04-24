from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

import pytest

from annofabcli.annotation_specs import add_attribute
from annofabcli.annotation_specs.add_attribute import ATTRIBUTE_TYPES, AddAttributeMain, create_attribute

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
    add_attribute.add_parser(subparsers)
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


class TestParseArgs:
    def test_parse_args__flag(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "add_attribute",
                "--project_id",
                "prj1",
                "--attribute_type",
                "flag",
                "--attribute_name_en",
                "weather",
                "--label_name_en",
                "car",
            ]
        )
        assert args.attribute_type == "flag"
        assert args.label_name_en == ["car"]

    def test_parse_args__choice_is_invalid(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "add_attribute",
                    "--project_id",
                    "prj1",
                    "--attribute_type",
                    "choice",
                    "--attribute_name_en",
                    "weather",
                    "--label_name_en",
                    "car",
                ]
            )

    def test_attribute_types(self) -> None:
        assert ATTRIBUTE_TYPES == ["comment", "flag", "integer", "link", "text", "tracking"]


class TestCreateAttribute:
    def test_create_attribute__flag(self) -> None:
        actual = create_attribute(
            attribute_type="flag",
            attribute_name_en="unclear2",
            attribute_name_ja="不明",
            attribute_id="unclear2_attr",
        )

        assert actual["type"] == "flag"
        assert actual["default"] is False
        assert actual["choices"] == []

    def test_create_attribute__text(self) -> None:
        actual = create_attribute(
            attribute_type="text",
            attribute_name_en="note",
            attribute_name_ja="メモ",
            attribute_id="note_attr",
        )

        assert actual["type"] == "text"
        assert actual["default"] == ""
        assert actual["choices"] == []


class TestAddAttributeMain:
    def test_add_attribute__flag(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_attribute(
            attribute_type="flag",
            attribute_name_en="weather_checked",
            attribute_name_ja="天気確認済み",
            attribute_id="weather_checked_attr",
            label_ids=[],
            label_name_ens=["car"],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_attribute = service.api.last_put["additionals"][-1]
        assert added_attribute["additional_data_definition_id"] == "weather_checked_attr"
        assert added_attribute["type"] == "flag"
        assert added_attribute["default"] is False
        assert added_attribute["choices"] == []

        car_label = next(label for label in service.api.last_put["labels"] if label["label_id"] == "car_label_id")
        assert "weather_checked_attr" in car_label["additional_data_definitions"]
        assert "以下の属性を追加しました。" in service.api.last_put["comment"]

    def test_add_attribute__text(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        result = main.add_attribute(
            attribute_type="text",
            attribute_name_en="note",
            attribute_name_ja="メモ",
            attribute_id="note_attr",
            label_ids=[],
            label_name_ens=["car"],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        added_attribute = service.api.last_put["additionals"][-1]
        assert added_attribute["type"] == "text"
        assert added_attribute["default"] == ""
        assert added_attribute["choices"] == []

    def test_add_attribute__attribute_id_is_uuidv4_when_not_specified(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        main.add_attribute(
            attribute_type="text",
            attribute_name_en="note2",
            attribute_name_ja=None,
            attribute_id=None,
            label_ids=["car_label_id"],
            label_name_ens=[],
            comment="custom",
        )

        assert service.api.last_put is not None
        generated_attribute_id = service.api.last_put["additionals"][-1]["additional_data_definition_id"]
        assert str(uuid.UUID(generated_attribute_id, version=4)) == generated_attribute_id

    def test_add_attribute__duplicated_attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddAttributeMain(service, project_id="prj1", all_yes=True)  # type: ignore

        with pytest.raises(ValueError):
            main.add_attribute(
                attribute_type="flag",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                label_ids=["car_label_id"],
                label_name_ens=[],
            )
