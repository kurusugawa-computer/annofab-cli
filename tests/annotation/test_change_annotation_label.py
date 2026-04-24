from __future__ import annotations

import argparse
import copy

import pytest

from annofabcli.annotation import change_annotation_label
from annofabcli.annotation.change_annotation_label import ChangeAnnotationLabelMain, DestLabelInfo, get_label_id_from_name_or_id, is_allowed_label_change

ANNOTATION_SPECS = {
    "labels": [
        {
            "label_id": "label_car",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "自動車"}, {"lang": "en-US", "message": "car"}],
                "default_lang": "ja-JP",
            },
            "annotation_type": "polygon",
            "additional_data_definitions": ["attr_common", "attr_src_only"],
        },
        {
            "label_id": "label_bus",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "バス"}, {"lang": "en-US", "message": "bus"}],
                "default_lang": "ja-JP",
            },
            "annotation_type": "polygon",
            "additional_data_definitions": ["attr_common", "attr_dest_only"],
        },
        {
            "label_id": "label_road",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "道路"}, {"lang": "en-US", "message": "road"}],
                "default_lang": "ja-JP",
            },
            "annotation_type": "polyline",
            "additional_data_definitions": ["attr_common"],
        },
        {
            "label_id": "label_box",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "矩形"}, {"lang": "en-US", "message": "box"}],
                "default_lang": "ja-JP",
            },
            "annotation_type": "bounding_box",
            "additional_data_definitions": ["attr_common"],
        },
    ],
    "additionals": [
        {
            "additional_data_definition_id": "attr_common",
            "name": {"messages": [{"lang": "en-US", "message": "common"}], "default_lang": "en-US"},
        },
        {
            "additional_data_definition_id": "attr_src_only",
            "name": {"messages": [{"lang": "en-US", "message": "src_only"}], "default_lang": "en-US"},
        },
        {
            "additional_data_definition_id": "attr_dest_only",
            "name": {"messages": [{"lang": "en-US", "message": "dest_only"}], "default_lang": "en-US"},
        },
    ],
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
    def test_get_dest_label_info(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True, annotation_specs=ANNOTATION_SPECS)  # type: ignore[arg-type]

        actual = main.get_dest_label_info("label_bus")

        assert actual == DestLabelInfo(
            label_id="label_bus",
            annotation_type="polygon",
            additional_data_definition_ids={"attr_common", "attr_dest_only"},
        )

    def test_change_annotation_label(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True, annotation_specs=ANNOTATION_SPECS)  # type: ignore[arg-type]
        dest_label_info = main.get_dest_label_info("label_bus")

        annotation_list = [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-04-24T00:00:00+09:00",
                "detail": {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [
                        {"additional_data_definition_id": "attr_common", "value": "keep"},
                        {"additional_data_definition_id": "attr_src_only", "value": "remove"},
                    ],
                },
            }
        ]
        main.change_annotation_label(annotation_list, dest_label_info)

        assert service.api.request_body == [
            {
                "data": {
                    "project_id": "prj1",
                    "task_id": "task1",
                    "input_data_id": "input1",
                    "updated_datetime": "2026-04-24T00:00:00+09:00",
                    "annotation_id": "anno1",
                    "label_id": "label_bus",
                    "additional_data_list": [{"additional_data_definition_id": "attr_common", "value": "keep"}],
                },
                "_type": "PutV2",
            }
        ]

    def test_get_target_task_id_list__when_task_id_is_none(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True, annotation_specs=ANNOTATION_SPECS)  # type: ignore[arg-type]

        actual = main.get_target_task_id_list(None)
        assert actual == ["task1", "task2"]

    def test_change_annotation_label__allows_polygon_to_polyline(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True, annotation_specs=ANNOTATION_SPECS)  # type: ignore[arg-type]
        dest_label_info = main.get_dest_label_info("label_road")

        annotation_list = [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-04-24T00:00:00+09:00",
                "detail": {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [{"additional_data_definition_id": "attr_common", "value": "keep"}],
                },
            }
        ]

        main.change_annotation_label(annotation_list, dest_label_info)

        assert service.api.request_body is not None
        assert service.api.request_body[0]["data"]["label_id"] == "label_road"

    def test_change_annotation_label__raises_when_annotation_type_is_not_compatible(self) -> None:
        service = DummyService()
        main = ChangeAnnotationLabelMain(service, project_id="prj1", include_complete_task=False, all_yes=True, annotation_specs=ANNOTATION_SPECS)  # type: ignore[arg-type]
        dest_label_info = main.get_dest_label_info("label_box")

        annotation_list = [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-04-24T00:00:00+09:00",
                "detail": {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [],
                },
            }
        ]

        with pytest.raises(ValueError):
            main.change_annotation_label(annotation_list, dest_label_info)


class TestIsAllowedLabelChange:
    @pytest.mark.parametrize(
        ("src_annotation_type", "dest_annotation_type"),
        [
            ("polygon", "polygon"),
            ("polygon", "polyline"),
            ("polyline", "polygon"),
            ("segmentation", "segmentation_v2"),
            ("segmentation_v2", "segmentation"),
            ("user_instance_segment", "user_semantic_segment"),
            ("user_semantic_segment", "user_instance_segment"),
        ],
    )
    def test_true(self, src_annotation_type: str, dest_annotation_type: str) -> None:
        assert is_allowed_label_change(src_annotation_type, dest_annotation_type)

    @pytest.mark.parametrize(
        ("src_annotation_type", "dest_annotation_type"),
        [
            ("polygon", "bounding_box"),
            ("segmentation", "polygon"),
            ("user_instance_segment", "segmentation"),
        ],
    )
    def test_false(self, src_annotation_type: str, dest_annotation_type: str) -> None:
        assert not is_allowed_label_change(src_annotation_type, dest_annotation_type)

    def test_directional_conversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            change_annotation_label,
            "ALLOWED_ANNOTATION_TYPE_CONVERSIONS",
            {("polygon", "polyline")},
        )

        assert is_allowed_label_change("polygon", "polyline")
        assert not is_allowed_label_change("polyline", "polygon")
