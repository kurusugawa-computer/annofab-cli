from __future__ import annotations

import argparse
import json
import logging
from contextlib import nullcontext
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest

from annofabcli.annotation.change_annotation_attributes_per_annotation import (
    ChangeAnnotationAttributesPerAnnotationMain,
    ChangeAttributesPerAnnotation,
    TargetAnnotation,
    filter_annotation_items_by_task_ids,
)
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.common.exceptions import AnnofabCliException


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


@pytest.mark.parametrize("failure", ["none", "get_task"])
@pytest.mark.parametrize("parallelism", [None, 2])
def test_task_parallelism_preserves_backup_order_and_status_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture, parallelism: int | None, failure: str) -> None:
    service = Mock()
    barrier = Barrier(2)
    updates: list[tuple[str, str]] = []

    def get_task(_project_id, task_id):
        if failure == "get_task" and task_id == "task1":
            raise RuntimeError("task API failure")
        if failure == "none" and parallelism is not None and task_id in {"task1", "task2"}:
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
                    "details": [{"annotation_id": "annotation1", "label_id": "label_car", "additional_data_list": [], "body": {"_type": "Inner", "data": {"_type": "Range", "begin": 0, "end": 1}}}],
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
        assert request_body[0]["data"]["additional_data_list"] == []
        updates.append((task_id, input_id))
        return {}, None

    service.wrapper.get_task_or_none.side_effect = get_task
    service.api.get_editor_annotations_in_bulk.side_effect = get_annotations
    service.api.batch_update_annotations.side_effect = update
    service.api.get_annotation_specs.return_value = ({"additionals": []}, None)
    main_obj = ChangeAnnotationAttributesPerAnnotationMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=False, all_yes=True, backup_dir=tmp_path)
    items = [
        TargetAnnotation(task_id=task_id, input_data_id=input_id, annotation_id="annotation1", attributes={})
        for task_id, input_id in [("task1", "input1"), ("task1", "input2"), ("task2", "input1"), ("complete", "input1")]
    ]

    expected_error = failure == "get_task"
    with caplog.at_level(logging.INFO), pytest.raises(AnnofabCliException) if expected_error else nullcontext():
        main_obj.change_annotation_attributes(items, parallelism=parallelism)

    expected_updates = [("task2", "input1")] if failure == "get_task" else [("task1", "input1"), ("task1", "input2"), ("task2", "input1")]
    assert sorted(updates) == expected_updates
    assert [input_id for task_id, input_id in updates if task_id == "task1"] == ([] if failure == "get_task" else ["input1", "input2"])
    assert not (tmp_path / "complete").exists()
    assert "タスクが完了状態" in caplog.text
    assert ("1/4" if failure == "get_task" else "3/4") in caplog.messages[-1]
    if expected_error:
        assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)


def test_parallelism_requires_yes_before_accessing_api() -> None:
    service = Mock()
    args = argparse.Namespace(parallelism=2, yes=False)
    command = ChangeAttributesPerAnnotation(service, Mock(), args)

    with pytest.raises(SystemExit) as exc_info:
        command.main()

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    service.api.get_annotation_specs.assert_not_called()
