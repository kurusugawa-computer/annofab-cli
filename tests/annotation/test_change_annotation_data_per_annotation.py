from __future__ import annotations

from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_data_per_annotation import (
    ChangeAnnotationDataCount,
    ChangeAnnotationDataPerAnnotationMain,
    TargetAnnotationData,
    create_request_body_for_change_data,
    get_annotation_data_list_per_task_id_input_data_id,
)


def test_get_annotation_data_list_per_task_id_input_data_id() -> None:
    annotation_list = [
        TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000}),
        TargetAnnotationData(task_id="task1", input_data_id="input2", annotation_id="anno2", data={"_type": "Range", "begin": 2000, "end": 6000}),
        TargetAnnotationData(task_id="task2", input_data_id="input3", annotation_id="anno3", data={"_type": "Range", "begin": 3000, "end": 7000}),
    ]

    actual = get_annotation_data_list_per_task_id_input_data_id(annotation_list)

    assert actual["task1"]["input1"] == [annotation_list[0]]
    assert actual["task1"]["input2"] == [annotation_list[1]]
    assert actual["task2"]["input3"] == [annotation_list[2]]


class TestCreateRequestBodyForChangeData:
    def test_create_request_body(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "_type": "Update",
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "additional_data_list": [{"definition_id": "attr1", "value": "foo"}],
                    "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 0, "end": 1000}},
                    "editor_props": {"is_protected": False},
                },
                {
                    "_type": "Update",
                    "annotation_id": "anno2",
                    "label_id": "label1",
                    "additional_data_list": [],
                    "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 2000, "end": 3000}},
                    "editor_props": {},
                },
            ],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]

        actual = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual.count == ChangeAnnotationDataCount(success=1, failed=0)
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
                    "label_id": "label1",
                    "additional_data_list": [{"definition_id": "attr1", "value": "foo"}],
                    "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 1000, "end": 5000}},
                    "editor_props": {"is_protected": False},
                },
                {
                    "_type": "Update",
                    "annotation_id": "anno2",
                    "label_id": "label1",
                    "additional_data_list": [],
                    "body": None,
                    "editor_props": {},
                },
            ],
        }

    def test_skip_when_annotation_does_not_exist(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]

        actual = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual.request_body["details"] == []
        assert actual.count == ChangeAnnotationDataCount(success=0, failed=1)


class TestChangeAnnotationDataPerAnnotationMain:
    def test_change_annotation_data_by_frame_uses_put_annotation(self) -> None:
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
                        "label_id": "label1",
                        "additional_data_list": [],
                        "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 0, "end": 1000}},
                        "editor_props": {},
                    }
                ],
            },
            None,
        )
        main_obj = ChangeAnnotationDataPerAnnotationMain(service, project_id="prj1", include_complete_task=False, include_on_hold_task=False, all_yes=True)

        actual = main_obj.change_annotation_data_by_frame(
            "task1",
            "input1",
            [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})],
        )

        assert actual == ChangeAnnotationDataCount(success=1, failed=0)
        service.api.batch_update_annotations.assert_not_called()
        service.api.put_annotation.assert_called_once()
        _, args, kwargs = service.api.put_annotation.mock_calls[0]
        assert args[:3] == ("prj1", "task1", "input1")
        assert kwargs["query_params"] == {"v": "2"}

    def test_change_annotation_data_for_task_skips_on_hold_task_by_default(self) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {"task_id": "task1", "status": "on_hold"}
        main_obj = ChangeAnnotationDataPerAnnotationMain(service, project_id="prj1", include_complete_task=False, include_on_hold_task=False, all_yes=True)

        actual_is_changeable, actual_count = main_obj.change_annotation_data_for_task(
            "task1",
            {"input1": [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]},
        )

        assert actual_is_changeable is False
        assert actual_count == ChangeAnnotationDataCount(success=0, failed=1)

    def test_change_annotation_data_for_task_allows_on_hold_task_when_option_is_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = Mock()
        service.wrapper.get_task_or_none.return_value = {"task_id": "task1", "status": "on_hold"}
        main_obj = ChangeAnnotationDataPerAnnotationMain(service, project_id="prj1", include_complete_task=False, include_on_hold_task=True, all_yes=True)

        def change_annotation_data_by_frame(task_id: str, input_data_id: str, anno_list: list[TargetAnnotationData]) -> ChangeAnnotationDataCount:
            assert task_id == "task1"
            assert input_data_id == "input1"
            assert len(anno_list) == 1
            return ChangeAnnotationDataCount(success=1, failed=0)

        monkeypatch.setattr(main_obj, "change_annotation_data_by_frame", change_annotation_data_by_frame)

        actual_is_changeable, actual_count = main_obj.change_annotation_data_for_task(
            "task1",
            {"input1": [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]},
        )

        assert actual_is_changeable is True
        assert actual_count == ChangeAnnotationDataCount(success=1, failed=0)

    def test_skip_when_data_type_is_changed(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "additional_data_list": [],
                    "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 0, "end": 1000}},
                    "editor_props": {},
                }
            ],
        }
        annotation_list = [
            TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 100, "y": 200}})
        ]

        actual = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual.count == ChangeAnnotationDataCount(success=0, failed=1)
        assert actual.request_body["details"][0]["body"] is None

    def test_skip_when_outer_annotation(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "additional_data_list": [],
                    "body": {"_type": "Outer", "path": "s3/path"},
                    "editor_props": {},
                }
            ],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "SegmentationV2", "data_uri": "outer2"})]

        actual = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual.count == ChangeAnnotationDataCount(success=0, failed=1)
        assert actual.request_body["details"][0]["body"] is None
