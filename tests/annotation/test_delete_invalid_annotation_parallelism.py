from __future__ import annotations

import argparse
import json
import logging
from functools import partial
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pytest

from annofabcli.annotation.delete_invalid_attribute_value import DeleteInvalidAttributeValueMain, DeleteInvalidAttributeValueOfAnnotation
from annofabcli.annotation.delete_invalid_label_annotation import DeleteInvalidLabelAnnotationMain, DeleteInvalidLabelAnnotationOfAnnotation
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE


def get_project(_project_id: str) -> tuple[dict, None]:
    return {"title": "test project"}, None


def get_task(_project_id: str, task_id: str) -> dict:
    if task_id == "failed":
        raise RuntimeError("API failure")
    return {
        "project_id": "prj1",
        "task_id": task_id,
        "phase": "annotation",
        "phase_stage": 1,
        "status": "complete" if task_id == "complete" else "break",
        "input_data_id_list": ["input1"],
        "account_id": None,
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2026-01-01T00:00:00Z",
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": {},
    }


def get_editor_annotation(project_id: str, task_id: str, input_data_id: str, **_kwargs) -> tuple[dict, None]:
    return {
        "project_id": project_id,
        "task_id": task_id,
        "input_data_id": input_data_id,
        "updated_datetime": "2026-01-01T00:00:00Z",
        "format_version": "2.0.0",
        "details": [
            {
                "annotation_id": "anno1",
                "label_id": "label1",
                "body": {"_type": "Inner", "data": {}},
                "additional_data_list": [{"definition_id": "invalid_attribute", "value": "test"}],
            }
        ],
    }, None


def get_editor_annotations_in_bulk(project_id: str, task_id: str, **_kwargs) -> tuple[dict, None]:
    annotation, _ = get_editor_annotation(project_id, task_id, "input1")
    return {"success": [annotation], "failure": []}, None


def record_update(output_dir: Path, _project_id: str, *_args, request_body: dict | list[dict], **_kwargs) -> tuple[dict, None]:
    task_id = request_body[0]["task_id"] if isinstance(request_body, list) else request_body["task_id"]
    # バックアップが書き込まれる前に更新APIを呼ばないことも確認する。
    assert (output_dir / "backup" / task_id / "input1.json").is_file()
    (output_dir / f"{task_id}.json").write_text(json.dumps(request_body), encoding="utf-8")
    return {}, None


@pytest.mark.parametrize("parallelism", [None, 2])
@pytest.mark.parametrize("command", ["attribute", "label"])
def test_multiple_tasks_preserve_backup_skip_and_continue_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, parallelism, command):
    # 実際のスレッドプールで実行し、API境界だけを置き換える。
    service = annofabapi.build(pat="test")
    monkeypatch.setattr(service.api, "get_project", get_project)
    monkeypatch.setattr(service.wrapper, "get_task_or_none", get_task)
    monkeypatch.setattr(service.api, "get_editor_annotation", get_editor_annotation)
    monkeypatch.setattr(service.api, "get_editor_annotations_in_bulk", get_editor_annotations_in_bulk)
    monkeypatch.setattr(service.api, "put_annotation", partial(record_update, tmp_path))
    monkeypatch.setattr(service.api, "batch_update_annotations", partial(record_update, tmp_path))
    caplog.set_level(logging.INFO)

    if command == "attribute":
        attribute_obj = DeleteInvalidAttributeValueMain(service, project_id="prj1", include_complete_task=False, all_yes=True)
        attribute_obj.delete_attribute_value_for_task_list(
            ["task1", "failed", "complete", "task2", "task1"], allowed_attribute_ids_by_label_id={"label1": set()}, backup_dir=tmp_path / "backup", parallelism=parallelism
        )
    else:
        label_obj = DeleteInvalidLabelAnnotationMain(service, project_id="prj1", include_complete_task=False, all_yes=True)
        label_obj.delete_invalid_label_annotation_for_task_list(["task1", "failed", "complete", "task2", "task1"], existing_label_ids=set(), backup_dir=tmp_path / "backup", parallelism=parallelism)

    assert sorted(p.stem for p in tmp_path.glob("*.json")) == ["task1", "task2"]
    assert sorted(p.name for p in (tmp_path / "backup").iterdir()) == ["task1", "task2"]
    for task_id in ["task1", "task2"]:
        backup = json.loads((tmp_path / "backup" / task_id / "input1.json").read_text())
        update = json.loads((tmp_path / f"{task_id}.json").read_text())
        assert backup["details"][0]["additional_data_list"][0]["definition_id"] == "invalid_attribute"
        if command == "attribute":
            assert update["details"][0]["additional_data_list"] == []
        else:
            assert update[0]["_type"] == "Delete"
    assert "タスクが完了状態のため、スキップします。" in caplog.text
    assert any(record.levelno == logging.WARNING and record.exc_info is not None and "failed" in record.message for record in caplog.records)
    assert "2 / 4 件のタスク" in caplog.text
    assert "2 件" in caplog.messages[-1]


@pytest.mark.parametrize("command_class", [DeleteInvalidAttributeValueOfAnnotation, DeleteInvalidLabelAnnotationOfAnnotation])
def test_parallelism_requires_yes_before_accessing_project(command_class):
    service = Mock()
    args = argparse.Namespace(parallelism=2, yes=False)
    command = command_class(service, Mock(), args)

    with pytest.raises(SystemExit) as exc_info:
        command.main()

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    service.api.get_annotation_specs.assert_not_called()
