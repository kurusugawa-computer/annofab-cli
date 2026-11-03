from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_label_per_annotation import (
    ChangeAnnotationLabelPerAnnotationMain,
    ChangeLabelPerAnnotation,
    TargetAnnotationLabel,
    TargetAnnotationLabelInput,
    filter_annotation_items_by_task_ids,
    resolve_target_annotation_list,
)
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE

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


@pytest.mark.parametrize("parallelism", [None, 2])
def test_task_parallelism_preserves_backup_order_and_status_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture, parallelism: int | None) -> None:
    service = Mock()
    barrier = Barrier(2)
    updates: list[tuple[str, str]] = []

    def get_task(_project_id, task_id):
        if parallelism is not None and task_id in {"task1", "task2"}:
            barrier.wait(timeout=10)
        return {"task_id": task_id, "status": "complete" if task_id == "complete" else "not_started", "account_id": None}

    def get_annotations(project_id, task_id, *, query_params):
        return {
            "success": [
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "input_data_id": input_id,
                    "updated_datetime": "2026-01-01T00:00:00Z",
                    "format_version": "2.0.0",
                    "details": [{"annotation_id": "annotation1", "label_id": "label_car", "additional_data_list": [], "body": {"_type": "Inner", "data": {}}}],
                }
                for input_id in query_params["input_data_id"].split(",")
            ],
            "failure": [],
        }, None

    def update(_project_id, *_args, request_body, **_kwargs):
        annotation = request_body[0]["data"]
        task_id, input_id = annotation["task_id"], annotation["input_data_id"]
        backup = json.loads((tmp_path / task_id / f"{input_id}.json").read_text())
        assert backup["input_data_id"] == input_id
        assert request_body[0]["data"]["label_id"] == "label_bus"
        updates.append((task_id, input_id))
        return {}, None

    service.wrapper.get_task_or_none.side_effect = get_task
    service.api.get_editor_annotations_in_bulk.side_effect = get_annotations
    service.api.batch_update_annotations.side_effect = update
    service.api.get_annotation_specs.return_value = (ANNOTATION_SPECS, None)
    main_obj = ChangeAnnotationLabelPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=False, all_yes=True, backup_dir=tmp_path)
    items = [
        TargetAnnotationLabel(task_id=task_id, input_data_id=input_id, annotation_id="annotation1", label_id="label_bus")
        for task_id, input_id in [("task1", "input1"), ("task1", "input2"), ("task2", "input1"), ("complete", "input1")]
    ]

    with caplog.at_level(logging.INFO):
        main_obj.change_annotation_label(items, parallelism=parallelism)

    assert sorted(updates) == [("task1", "input1"), ("task1", "input2"), ("task2", "input1")]
    assert [input_id for task_id, input_id in updates if task_id == "task1"] == ["input1", "input2"]
    assert not (tmp_path / "complete").exists()
    assert "タスクが完了状態" in caplog.text
    assert "3/4" in caplog.messages[-1]


def test_parallelism_requires_yes_before_accessing_api() -> None:
    service = Mock()
    args = argparse.Namespace(parallelism=2, yes=False)
    command = ChangeLabelPerAnnotation(service, Mock(), args)

    with pytest.raises(SystemExit) as exc_info:
        command.main()

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    service.api.get_annotation_specs.assert_not_called()
