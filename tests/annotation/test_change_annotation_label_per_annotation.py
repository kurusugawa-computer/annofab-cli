from __future__ import annotations

from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_label_per_annotation import (
    ChangeAnnotationLabelPerAnnotationMain,
    TargetAnnotationLabel,
    TargetAnnotationLabelInput,
    resolve_target_annotation_list,
)

ANNOTATION_SPECS = {
    "labels": [
        {
            "label_id": "label_car",
            "label_name": {"messages": [{"lang": "en-US", "message": "car"}], "default_lang": "en-US"},
            "annotation_type": "polygon",
            "additional_data_definitions": ["common", "car_only"],
        },
        {
            "label_id": "label_bus",
            "label_name": {"messages": [{"lang": "en-US", "message": "bus"}], "default_lang": "en-US"},
            "annotation_type": "polygon",
            "additional_data_definitions": ["common", "bus_only"],
        },
        {"label_id": "label_road", "label_name": {"messages": [{"lang": "en-US", "message": "road"}], "default_lang": "en-US"}, "annotation_type": "polyline", "additional_data_definitions": []},
    ],
    "additionals": [],
}


def create_main_obj() -> tuple[ChangeAnnotationLabelPerAnnotationMain, Mock]:
    service = Mock()
    service.api.get_annotation_specs.return_value = (ANNOTATION_SPECS, None)
    return ChangeAnnotationLabelPerAnnotationMain(service, project_id="project1", include_complete_task=False, all_yes=True), service


def test_change_annotation_label_by_frame_changes_label_and_removes_incompatible_attributes() -> None:
    main_obj, service = create_main_obj()
    editor_annotation = {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-09-07T00:00:00+09:00",
        "details": [
            {
                "annotation_id": "annotation1",
                "label_id": "label_car",
                "additional_data_list": [{"definition_id": "common", "value": "keep"}, {"definition_id": "car_only", "value": "remove"}],
            }
        ],
    }

    actual = main_obj.change_annotation_label_by_frame(
        "task1", "input1", [TargetAnnotationLabel(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="label_bus")], editor_annotation
    )

    assert actual.success == 1
    assert actual.skipped == 0
    assert actual.failed == 0
    assert service.api.batch_update_annotations.call_args.kwargs["request_body"][0]["data"] == {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-09-07T00:00:00+09:00",
        "annotation_id": "annotation1",
        "label_id": "label_bus",
        "additional_data_list": [{"definition_id": "common", "value": "keep"}],
    }


def test_change_annotation_label_by_frame_skips_incompatible_label_type() -> None:
    main_obj, service = create_main_obj()
    editor_annotation = {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-09-07T00:00:00+09:00",
        "details": [{"annotation_id": "annotation1", "label_id": "label_car", "additional_data_list": []}],
    }

    actual = main_obj.change_annotation_label_by_frame(
        "task1", "input1", [TargetAnnotationLabel(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="label_road")], editor_annotation
    )

    assert actual.success == 0
    assert actual.skipped == 1
    assert actual.failed == 0
    service.api.batch_update_annotations.assert_not_called()


def test_resolve_target_annotation_list_rejects_unknown_label() -> None:
    with pytest.raises(ValueError):
        resolve_target_annotation_list([TargetAnnotationLabelInput(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="unknown")], ANNOTATION_SPECS)


def test_resolve_target_annotation_list_rejects_duplicate_annotation() -> None:
    annotation = TargetAnnotationLabelInput(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="label_bus")
    with pytest.raises(ValueError):
        resolve_target_annotation_list([annotation, annotation], ANNOTATION_SPECS)


def test_resolve_target_annotation_list_resolves_label_name() -> None:
    actual = resolve_target_annotation_list([TargetAnnotationLabelInput(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_name="bus")], ANNOTATION_SPECS)

    assert actual == [TargetAnnotationLabel(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="label_bus")]
