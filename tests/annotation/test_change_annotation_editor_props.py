from __future__ import annotations

import copy
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_editor_props import (
    ChangeAnnotationEditorPropsMain,
    ChangeEditorPropsCount,
    create_request_body_for_change_editor_props,
    get_annotation_ids_per_input_data_id,
    get_label_ids_from_label_names,
)

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
            "label_id": "label_road",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "道路"}, {"lang": "en-US", "message": "road"}],
                "default_lang": "ja-JP",
            },
        },
    ],
    "additionals": [],
}


class TestGetLabelIdsFromLabelNames:
    def test_get_label_ids_from_label_names(self) -> None:
        actual = get_label_ids_from_label_names(ANNOTATION_SPECS, {"car", "road"})

        assert actual == {"label_car", "label_road"}

    def test_get_label_ids_from_label_names__not_found(self) -> None:
        with pytest.raises(ValueError):
            get_label_ids_from_label_names(ANNOTATION_SPECS, {"bike"})

    def test_get_label_ids_from_label_names__multiple_label(self) -> None:
        annotation_specs = copy.deepcopy(ANNOTATION_SPECS)
        annotation_specs["labels"].append(copy.deepcopy(annotation_specs["labels"][0]))

        with pytest.raises(ValueError):
            get_label_ids_from_label_names(annotation_specs, {"car"})


def test_get_annotation_ids_per_input_data_id() -> None:
    annotation_list = [
        {"input_data_id": "input1", "detail": {"annotation_id": "anno1", "label_id": "label_car"}},
        {"input_data_id": "input1", "detail": {"annotation_id": "anno2", "label_id": "label_road"}},
        {"input_data_id": "input2", "detail": {"annotation_id": "anno3", "label_id": "label_car"}},
    ]

    actual = get_annotation_ids_per_input_data_id(annotation_list, {"label_car"})

    assert actual == {"input1": {"anno1"}, "input2": {"anno3"}}


class TestCreateRequestBodyForChangeEditorProps:
    def test_create_request_body(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [],
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "editor_props": {"can_delete": True, "can_edit_data": True},
                    "url": "https://example.com",
                },
                {
                    "annotation_id": "anno2",
                    "label_id": "label_road",
                    "additional_data_list": [],
                    "body": {"_type": "Outer", "path": "s3/path"},
                    "editor_props": {"can_delete": True},
                },
            ],
        }

        actual = create_request_body_for_change_editor_props(editor_annotation, {"anno1"}, {"can_delete": False})

        assert actual.count == ChangeEditorPropsCount(success=1, failed=0)
        assert actual.request_body == {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "format_version": "2.0.0",
            "details": [
                {
                    "_type": "Update",
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [],
                    "body": None,
                    "editor_props": {"can_delete": False, "can_edit_data": True},
                },
                {
                    "_type": "Update",
                    "annotation_id": "anno2",
                    "label_id": "label_road",
                    "additional_data_list": [],
                    "body": None,
                    "editor_props": {"can_delete": True},
                },
            ],
        }

    def test_create_request_body__when_editor_props_is_empty(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label_car",
                    "additional_data_list": [],
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "editor_props": {},
                },
            ],
        }

        actual = create_request_body_for_change_editor_props(editor_annotation, {"anno1"}, {"can_edit_data": False})

        assert actual.count == ChangeEditorPropsCount(success=1, failed=0)
        assert actual.request_body["details"][0]["editor_props"] == {"can_edit_data": False}

    def test_create_request_body__skip_when_annotation_does_not_exist(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [],
        }

        actual = create_request_body_for_change_editor_props(editor_annotation, {"anno1"}, {"can_delete": False})

        assert actual.count == ChangeEditorPropsCount(success=0, failed=1)
        assert actual.request_body["details"] == []


class TestChangeAnnotationEditorPropsMain:
    def test_change_editor_props_for_task_skips_break_task_by_default(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {
            "task_id": "task1",
            "phase": "annotation",
            "status": "break",
            "account_id": "operator1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
        }
        main_obj = ChangeAnnotationEditorPropsMain(
            service,
            project_id="prj1",
            target_label_ids={"label_car"},
            editor_props={"can_delete": False},
            change_operator_to_me=True,
            include_complete_task=False,
            include_break_task=False,
            include_on_hold_task=False,
            all_yes=True,
        )

        actual = main_obj.change_editor_props_for_task("task1")

        assert actual == (False, ChangeEditorPropsCount(success=0, failed=0))
        service.wrapper.change_task_operator.assert_not_called()
        service.api.put_annotation.assert_not_called()

    def test_change_editor_props_by_input_data_uses_put_annotation(self) -> None:
        service = Mock()
        service.api.get_editor_annotation.return_value = (
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-05-22T00:00:00+09:00",
                "details": [
                    {
                        "annotation_id": "anno1",
                        "label_id": "label_car",
                        "additional_data_list": [],
                        "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                        "editor_props": {"can_delete": True},
                    }
                ],
            },
            None,
        )
        main_obj = ChangeAnnotationEditorPropsMain(
            service,
            project_id="prj1",
            target_label_ids={"label_car"},
            editor_props={"can_delete": False},
            change_operator_to_me=False,
            include_complete_task=False,
            include_break_task=False,
            include_on_hold_task=False,
            all_yes=True,
        )

        actual = main_obj.change_editor_props_by_input_data("task1", "input1", {"anno1"})

        assert actual == ChangeEditorPropsCount(success=1, failed=0)
        service.api.put_annotation.assert_called_once()
        _, args, kwargs = service.api.put_annotation.mock_calls[0]
        assert args[:3] == ("prj1", "task1", "input1")
        assert kwargs["query_params"] == {"v": "2"}
