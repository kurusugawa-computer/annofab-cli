from __future__ import annotations

import pytest

from annofabcli.annotation.change_annotation_data_per_annotation import (
    TargetAnnotationData,
    create_request_body_for_change_data,
    get_annotation_data_list_per_task_id_input_data_id,
    validate_target_data,
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


class TestValidateTargetData:
    def test_return_data_type(self) -> None:
        actual = validate_target_data({"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 100, "y": 200}}, annotation_id="anno1")
        assert actual == "BoundingBox"

    def test_raise_when_data_type_is_missing(self) -> None:
        with pytest.raises(TypeError):
            validate_target_data({"begin": 1000, "end": 5000}, annotation_id="anno1")

    def test_raise_when_data_type_is_unsupported(self) -> None:
        with pytest.raises(ValueError):
            validate_target_data({"_type": "SegmentationV2", "data_uri": "outer1"}, annotation_id="anno1")


class TestCreateRequestBodyForChangeData:
    def test_create_request_body(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "additional_data_list": [{"definition_id": "attr1", "value": "foo"}],
                    "data": {"_type": "Range", "begin": 0, "end": 1000},
                    "data_holding_type": "inline",
                }
            ],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]

        actual_request_body, actual_failed_count = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual_failed_count == 0
        assert actual_request_body == [
            {
                "data": {
                    "project_id": "prj1",
                    "task_id": "task1",
                    "input_data_id": "input1",
                    "updated_datetime": "2026-05-22T00:00:00+09:00",
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "additional_data_list": [{"definition_id": "attr1", "value": "foo"}],
                    "data": {"_type": "Range", "begin": 1000, "end": 5000},
                },
                "_type": "PutV2",
            }
        ]

    def test_skip_when_annotation_does_not_exist(self) -> None:
        editor_annotation = {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-05-22T00:00:00+09:00",
            "details": [],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "Range", "begin": 1000, "end": 5000})]

        actual_request_body, actual_failed_count = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual_request_body == []
        assert actual_failed_count == 1

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
                    "data": {"_type": "Range", "begin": 0, "end": 1000},
                    "data_holding_type": "inline",
                }
            ],
        }
        annotation_list = [
            TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 100, "y": 200}})
        ]

        actual_request_body, actual_failed_count = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual_request_body == []
        assert actual_failed_count == 1

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
                    "data": {"_type": "SegmentationV2", "data_uri": "outer1"},
                    "data_holding_type": "outer",
                }
            ],
        }
        annotation_list = [TargetAnnotationData(task_id="task1", input_data_id="input1", annotation_id="anno1", data={"_type": "SegmentationV2", "data_uri": "outer2"})]

        actual_request_body, actual_failed_count = create_request_body_for_change_data(editor_annotation, annotation_list)

        assert actual_request_body == []
        assert actual_failed_count == 1
