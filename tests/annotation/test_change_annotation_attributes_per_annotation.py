from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_attributes_per_annotation import (
    ChangeAnnotationAttributesPerAnnotationMain,
    TargetAnnotation,
    filter_annotation_items_by_task_ids,
)


def test_filter_annotation_items_by_task_ids() -> None:
    items = [
        TargetAnnotation(task_id="task1", input_data_id="input1", annotation_id="annotation1", attributes={}),
        TargetAnnotation(task_id="task2", input_data_id="input1", annotation_id="annotation2", attributes={}),
        TargetAnnotation(task_id="task1", input_data_id="input2", annotation_id="annotation3", attributes={}),
    ]

    actual_items, actual_not_existing_task_ids = filter_annotation_items_by_task_ids(items, ["task1", "task3"])

    assert actual_items == [items[0], items[2]]
    assert actual_not_existing_task_ids == {"task3"}


def test_change_annotation_attributes_logs_each_task_progress(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({}, None)
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=False, all_yes=True)
    monkeypatch.setattr(main_obj, "change_annotation_attributes_for_task", Mock(return_value=(True, 1, 0)))
    annotation_list = [TargetAnnotation(task_id=f"task_{index:03d}", input_data_id="input1", annotation_id="annotation1", attributes={}) for index in range(3)]

    with caplog.at_level(logging.INFO):
        main_obj.change_annotation_attributes(annotation_list)

    assert "1 / 3 件目 :: task_id='task_000' のアノテーションの属性値を変更します。" in caplog.text
    assert "2 / 3 件目 :: task_id='task_001' のアノテーションの属性値を変更します。" in caplog.text
    assert "3 / 3 件目 :: task_id='task_002' のアノテーションの属性値を変更します。" in caplog.text


def test_change_annotation_attributes_by_frame_does_not_log_skip_when_all_attributes_are_changed(caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({"additionals": []}, None)
    service.api.get_editor_annotation.return_value = (
        {
            "project_id": "project1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-08-30T23:17:58+09:00",
            "details": [{"annotation_id": "annotation1", "label_id": "label1"}],
        },
        None,
    )
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=False, all_yes=True)

    with caplog.at_level(logging.DEBUG):
        actual = main_obj.change_annotation_attributes_by_frame(
            "task1",
            "input1",
            [TargetAnnotation(task_id="task1", input_data_id="input1", annotation_id="annotation1", attributes={})],
        )

    assert actual == (1, 0)
    assert "1/1件の属性値を変更しました。" in caplog.text
    assert "属性値の変更をスキップしました。" not in caplog.text


@pytest.mark.parametrize(
    ("status", "include_on_hold_task", "expected_changed"),
    [("on_hold", False, False), ("on_hold", True, True), ("working", True, False), ("complete", True, False), ("not_started", False, True), ("break", False, True)],
)
def test_change_annotation_attributes_for_task_respects_task_status(status: str, *, include_on_hold_task: bool, expected_changed: bool) -> None:
    service = Mock()
    service.api.get_annotation_specs.return_value = ({"additionals": []}, None)
    service.wrapper.get_task_or_none.return_value = {"task_id": "task1", "status": status}
    editor_annotation = {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-08-30T23:17:58+09:00",
        "details": [{"annotation_id": "annotation1", "label_id": "label1"}],
    }
    service.api.get_editor_annotations_in_bulk.return_value = ({"success": [editor_annotation], "failure": []}, None)
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=include_on_hold_task, all_yes=True)
    target = TargetAnnotation(task_id="task1", input_data_id="input1", annotation_id="annotation1", attributes={})

    actual = main_obj.change_annotation_attributes_for_task("task1", {"input1": [target]})

    assert actual == (expected_changed, int(expected_changed), int(not expected_changed))
    if expected_changed:
        assert service.api.batch_update_annotations.call_args.kwargs["request_body"][0]["data"]["annotation_id"] == "annotation1"
    else:
        service.api.get_editor_annotations_in_bulk.assert_not_called()
        service.api.batch_update_annotations.assert_not_called()
