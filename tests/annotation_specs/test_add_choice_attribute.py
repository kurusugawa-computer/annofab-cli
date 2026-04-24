from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

import pytest

from annofabcli.annotation_specs.add_choice_attribute import (
    AddChoiceAttributeMain,
    build_choices,
    read_choices_csv,
    read_choices_json,
)
from annofabcli.annotation_specs import add_choice_attribute

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
    add_choice_attribute.add_parser(subparsers)
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
    def test_parse_args(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "add_choice_attribute",
                "--project_id",
                "prj1",
                "--attribute_type",
                "choice",
                "--attribute_name_en",
                "weather",
                "--choices_json",
                '[{"choice_name_en":"sunny"}]',
                "--label_name_en",
                "car",
                "--label_id",
                "label1",
            ]
        )
        assert args.attribute_type == "choice"
        assert args.label_name_en == ["car"]
        assert args.label_id == ["label1"]

    def test_parse_args__required(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["add_choice_attribute", "--project_id", "prj1"])

    def test_parse_args__choices_json_and_csv_are_mutually_exclusive(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "add_choice_attribute",
                    "--project_id",
                    "prj1",
                    "--attribute_type",
                    "choice",
                    "--attribute_name_en",
                    "weather",
                    "--choices_json",
                    '[{"choice_name_en":"sunny"}]',
                    "--choices_csv",
                    "choices.csv",
                ]
            )


class TestReadChoicesJson:
    def test_read_choices_json(self) -> None:
        actual = read_choices_json('[{"choice_id":"front","choice_name_en":"front","choice_name_ja":"前","is_default":true}]')
        assert actual[0].choice_id == "front"
        assert actual[0].choice_name_en == "front"
        assert actual[0].choice_name_ja == "前"
        assert actual[0].is_default is True

    def test_read_choices_json__without_choice_id(self) -> None:
        actual = read_choices_json('[{"choice_name_en":"front"}]')
        assert actual[0].choice_id is None
        assert actual[0].is_default is False

    def test_read_choices_json__not_list(self) -> None:
        with pytest.raises(ValueError):
            read_choices_json('{"choice_name_en":"front"}')

    def test_read_choices_json__missing_choice_name_en(self) -> None:
        with pytest.raises(ValueError):
            read_choices_json('[{"choice_id":"front"}]')

    def test_build_choices__duplicated_choice_id(self) -> None:
        choices = read_choices_json('[{"choice_id":"dup","choice_name_en":"front"},{"choice_id":"dup","choice_name_en":"rear"}]')
        with pytest.raises(ValueError):
            build_choices(choices)

    def test_build_choices__multiple_default(self) -> None:
        choices = read_choices_json('[{"choice_name_en":"front","is_default":true},{"choice_name_en":"rear","is_default":true}]')
        with pytest.raises(ValueError):
            build_choices(choices)


class TestReadChoicesCsv:
    def test_read_choices_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text("choice_id,choice_name_en,choice_name_ja,is_default\nfront,front,前,true\n,rear,,false\n", encoding="utf-8")

        actual = read_choices_csv(csv_path)
        assert len(actual) == 2
        assert actual[0].choice_id == "front"
        assert actual[0].is_default is True
        assert actual[1].choice_id is None
        assert actual[1].choice_name_ja is None

    def test_read_choices_csv__required_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text("choice_id,is_default\nfront,true\n", encoding="utf-8")

        with pytest.raises(ValueError):
            read_choices_csv(csv_path)

    def test_read_choices_csv__invalid_is_default(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        csv_path.write_text("choice_name_en,is_default\nfront,yes\n", encoding="utf-8")

        with pytest.raises(ValueError):
            read_choices_csv(csv_path)


class TestAddChoiceAttributeMain:
    def test_add_choice_attribute(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        result = main.add_choice_attribute(
            attribute_type="choice",
            attribute_name_en="weather",
            attribute_name_ja="天気",
            attribute_id="weather_attr",
            choice_inputs=read_choices_json(
                '[{"choice_id":"sunny","choice_name_en":"sunny","choice_name_ja":"晴れ","is_default":true},{"choice_name_en":"cloudy"}]'
            ),
            label_ids=[],
            label_name_ens=["car"],
            comment=None,
        )

        assert result is True
        assert service.api.last_put is not None
        additionals = service.api.last_put["additionals"]
        labels = service.api.last_put["labels"]
        added_attribute = additionals[-1]
        assert added_attribute["additional_data_definition_id"] == "weather_attr"
        assert added_attribute["type"] == "choice"
        assert added_attribute["default"] == "sunny"
        assert len(added_attribute["choices"]) == 2

        car_label = next(label for label in labels if label["label_id"] == "car_label_id")
        bike_label = next(label for label in labels if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        assert "weather_attr" in car_label["additional_data_definitions"]
        assert "weather_attr" not in bike_label["additional_data_definitions"]
        assert service.api.last_put["comment"].startswith("以下の選択肢系属性を追加しました。")

    def test_add_choice_attribute__default_empty(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        main.add_choice_attribute(
            attribute_type="select",
            attribute_name_en="weather2",
            attribute_name_ja=None,
            attribute_id="weather_attr2",
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"},{"choice_name_en":"cloudy"}]'),
            label_ids=["car_label_id"],
            label_name_ens=[],
            comment="custom",
        )

        assert service.api.last_put is not None
        added_attribute = service.api.last_put["additionals"][-1]
        assert added_attribute["default"] == ""
        assert service.api.last_put["comment"] == "custom"

    def test_add_choice_attribute__attribute_id_is_uuidv4_when_not_specified(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        main.add_choice_attribute(
            attribute_type="select",
            attribute_name_en="weather_uuid",
            attribute_name_ja=None,
            attribute_id=None,
            choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
            label_ids=["car_label_id"],
            label_name_ens=[],
            comment="custom",
        )

        assert service.api.last_put is not None
        generated_attribute_id = service.api.last_put["additionals"][-1]["additional_data_definition_id"]
        assert str(uuid.UUID(generated_attribute_id, version=4)) == generated_attribute_id

    def test_add_choice_attribute__duplicated_attribute_id(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        with pytest.raises(ValueError):
            main.add_choice_attribute(
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=["car_label_id"],
                label_name_ens=[],
            )

    def test_add_choice_attribute__duplicated_attribute_name(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        with pytest.raises(ValueError):
            main.add_choice_attribute(
                attribute_type="choice",
                attribute_name_en="type",
                attribute_name_ja=None,
                attribute_id="weather_attr",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=["car_label_id"],
                label_name_ens=[],
            )

    def test_add_choice_attribute__ambiguous_label_name(self, annotation_specs: dict) -> None:
        duplicated_specs = copy.deepcopy(annotation_specs)
        duplicated_label = copy.deepcopy(duplicated_specs["labels"][0])
        duplicated_label["label_id"] = "duplicated-id"
        duplicated_specs["labels"].append(duplicated_label)
        service = DummyService(duplicated_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        with pytest.raises(ValueError):
            main.add_choice_attribute(
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="weather_attr",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=[],
                label_name_ens=["car"],
            )

    def test_add_choice_attribute__label_not_found(self, annotation_specs: dict) -> None:
        service = DummyService(annotation_specs)
        main = AddChoiceAttributeMain(service, project_id="prj1", all_yes=True)

        with pytest.raises(ValueError):
            main.add_choice_attribute(
                attribute_type="choice",
                attribute_name_en="weather",
                attribute_name_ja=None,
                attribute_id="weather_attr",
                choice_inputs=read_choices_json('[{"choice_name_en":"sunny"}]'),
                label_ids=["not-found"],
                label_name_ens=[],
            )
