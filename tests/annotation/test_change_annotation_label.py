from __future__ import annotations

import argparse
import copy

import pytest

from annofabcli.annotation import change_annotation_label
from annofabcli.annotation.change_annotation_label import ChangeAnnotationLabelMain, get_label_id_from_name_or_id

ANNOTATION_SPECS = {
    "labels": [
        {
            "label_id": "label_car",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                "default_lang": "ja-JP",
            },
        },
        {
            "label_id": "label_bus",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "バス"}, {"lang": "en-US", "message": "bus"}],
                "default_lang": "ja-JP",
            },
        },
    ]
}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand_name", required=True)
    change_annotation_label.add_parser(subparsers)
    return parser


class DummyApi:
    def __init__(self) -> None:
        self.request_body: list[dict] | None = None

    def batch_update_annotations(self, project_id: str, request_body: list[dict]) -> tuple[list[dict], None]:
        assert project_id == "prj1"
        self.request_body = copy.deepcopy(request_body)
        return request_body, None


class DummyWrapper:
    def get_all_tasks(self, project_id: str) -> list[dict]:
        assert project_id == "prj1"
        return [{"task_id": "task1"}, {"task_id": "task2"}]


class DummyService:
    def __init__(self) -> None:
        self.api = DummyApi()
        self.wrapper = DummyWrapper()


class TestParseArgs:
    def test_parse_args__label_name(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "change_label",
                "--project_id",
                "prj1",
                "--annotation_query",
                '{"label":"car"}',
                "--label_name",
                "bus",
            ]
        )
        assert args.project_id == "prj1"
        assert args.annotation_query == '{"label":"car"}'
        assert args.task_id is None
        assert args.label_name == "bus"
        assert args.label_id is None

    def test_parse_args__label_id(self) -> None:
        parser = create_parser()
        args = parser.parse_args(
            [
                "change_label",
                "--project_id",
                "prj1",
                "--task_id",
                "task1",
                "task2",
                "--annotation_query",
                '{"label":"car"}',
                "--label_id",
                "label_bus",
            ]
        )
        assert args.task_id == ["task1", "task2"]
        assert args.label_name is None
        assert args.label_id == "label_bus"

    def test_parse_args__label_name_or_label_id_is_required(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "change_label",
                    "--project_id",
                    "prj1",
                    "--annotation_query",
                    '{"label":"car"}',
                ]
            )

    def test_parse_args__label_name_and_label_id_are_mutually_exclusive(self) -> None:
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "change_label",
                    "--project_id",
                    "prj1",
                    "--annotation_query",
                    '{"label":"car"}',
                    "--label_name",
                    "bus",
                    "--label_id",
                    "label_bus",
                ]
            )


class TestGetLabelIdFromNameOrId:
    def test_get_label_id_from_label_name(self) -> None:
        actual = get_label_id_from_name_or_id(ANNOTATION_SPECS, label_name="bus")
        assert actual == "label_bus"

    def test_get_label_id_from_label_id(self) -> None:
        actual = get_label_id_from_name_or_id(ANNOTATION_SPECS, label_id="label_car")
        assert actual == "label_car"

    def test_get_label_id__not_found(self) -> None:
        with pytest.raises(ValueError):
            get_label_id_from_name_or_id(ANNOTATION_SPECS, label_name="truck")

    def test_get_label_id__multiple_label(self) -> None:
        annotation_specs = copy.deepcopy(ANNOTATION_SPECS)
        annotation_specs["labels"].append(copy.deepcopy(annotation_specs["labels"][0]))

        with pytest.raises(ValueError):
            get_label_id_from_name_or_id(annotation_specs, label_name="car")


class TestChangeAnnotationLabelMain:
    def test_change_annotation_label(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True)  # type: ignore[arg-type]

        annotation_list = [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-04-24T00:00:00+09:00",
                "additional_data_list": [],
                "detail": {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                },
            }
        ]
        main.change_annotation_label(annotation_list, "label_bus")

        assert service.api.request_body == [
            {
                "data": {
                    "project_id": "prj1",
                    "task_id": "task1",
                    "input_data_id": "input1",
                    "updated_datetime": "2026-04-24T00:00:00+09:00",
                    "annotation_id": "anno1",
                    "label_id": "label_bus",
                    "additional_data_list": [],
                },
                "_type": "PutV2",
            }
        ]

    def test_get_target_task_id_list__when_task_id_is_none(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True)  # type: ignore[arg-type]

        actual = main.get_target_task_id_list(None)
        assert actual == ["task1", "task2"]
