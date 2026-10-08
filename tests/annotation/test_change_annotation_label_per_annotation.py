from __future__ import annotations

from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_label_per_annotation import (
    ChangeAnnotationLabelPerAnnotationMain,
    TargetAnnotationLabel,
    TargetAnnotationLabelInput,
    filter_annotation_items_by_task_ids,
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
    "inspection_phrases": [],
}


def test_filter_annotation_items_by_task_ids() -> None:
    items = [
        TargetAnnotationLabelInput(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_name="car"),
        TargetAnnotationLabelInput(task_id="task2", input_data_id="input1", annotation_id="annotation2", label_name="car"),
        TargetAnnotationLabelInput(task_id="task1", input_data_id="input2", annotation_id="annotation3", label_name="car"),
    ]

    actual_items, actual_not_existing_task_ids = filter_annotation_items_by_task_ids(items, ["task1", "task3"])

    assert actual_items == [items[0], items[2]]
    assert actual_not_existing_task_ids == {"task3"}


def create_main_obj(*, include_on_hold_task: bool = False) -> tuple[ChangeAnnotationLabelPerAnnotationMain, Mock]:
    service = Mock()
    service.api.get_annotation_specs.return_value = (ANNOTATION_SPECS, None)
    return ChangeAnnotationLabelPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=include_on_hold_task, all_yes=True), service


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


@pytest.mark.parametrize(
    ("status", "include_on_hold_task", "expected_changed"),
    [("on_hold", False, False), ("on_hold", True, True), ("working", True, False), ("complete", True, False), ("not_started", False, True), ("break", False, True)],
)
def test_change_annotation_label_for_task_respects_task_status(status: str, *, include_on_hold_task: bool, expected_changed: bool) -> None:
    main_obj, service = create_main_obj(include_on_hold_task=include_on_hold_task)
    service.wrapper.get_task_or_none.return_value = {"task_id": "task1", "status": status}
    editor_annotation = {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-09-07T00:00:00+09:00",
        "details": [{"annotation_id": "annotation1", "label_id": "label_car", "additional_data_list": []}],
    }
    service.api.get_editor_annotations_in_bulk.return_value = ({"success": [editor_annotation], "failure": []}, None)
    target = TargetAnnotationLabel(task_id="task1", input_data_id="input1", annotation_id="annotation1", label_id="label_bus")

    actual_changed, actual_count = main_obj.change_annotation_label_for_task("task1", {"input1": [target]})

    assert actual_changed == expected_changed
    assert actual_count.success == int(expected_changed)
    assert actual_count.skipped == int(not expected_changed)
    assert actual_count.failed == 0
    if expected_changed:
        assert service.api.batch_update_annotations.call_args.kwargs["request_body"][0]["data"]["label_id"] == "label_bus"
    else:
        service.api.get_editor_annotations_in_bulk.assert_not_called()
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
