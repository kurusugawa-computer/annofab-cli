import logging
import threading
from unittest.mock import Mock

import annofabapi
import pytest
from annofabapi.models import ProjectMemberRole

from annofabcli.annotation.copy_annotation import CopyAnnotationMain, CopyTarget, CopyTargetByInputData, CopyTargetByTask, parse_copy_target


def test_thread_copy_preserves_batches_counts_annotations_and_worker_logs(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    service = annofabapi.build(pat="test")
    monkeypatch.setattr(service.api, "_request_wrapper", Mock(side_effect=AssertionError("Unexpected HTTP request")))
    monkeypatch.setattr(service.api, "get_my_account", Mock(return_value=({"account_id": "account1"}, None)))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": ProjectMemberRole.OWNER.value}, None)))
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    bulk_requests: list[list[str]] = []
    copied: list[str] = []

    def get_tasks(_project_id, *, query_params):
        task_ids = query_params["task_id"].split(",")
        bulk_requests.append(task_ids)
        return {"success": [{"task_id": task_id, "phase": "annotation", "status": "not_started", "account_id": None} for task_id in task_ids]}, None

    def get_annotation(project_id, task_id, input_data_id):
        assert threading.get_ident() != main_thread_id
        assert project_id == "project1"
        assert input_data_id == "input1"
        details = (
            []
            if task_id.startswith("dest")
            else [{"annotation_id": "anno1", "label_id": "label1", "data_holding_type": "inner", "data": {"_type": "Classification"}, "additional_data_list": [], "editor_props": {}}]
        )
        return {"details": details, "updated_datetime": "2026-01-01T00:00:00Z"}

    def put_annotation(_project_id, task_id, _input_data_id, *, request_body):
        assert request_body["details"][0]["label_id"] == "label1"
        assert request_body["updated_datetime"] == "2026-01-01T00:00:00Z"
        if task_id in {"dest0", "dest1"}:
            barrier.wait(timeout=10)
        if task_id == "dest0":
            raise RuntimeError("annotation API failure")
        copied.append(task_id)
        return {}, None

    monkeypatch.setattr(service.api, "get_tasks_in_bulk", Mock(side_effect=get_tasks))
    monkeypatch.setattr(service.wrapper, "get_editor_annotation_or_none", Mock(side_effect=get_annotation))
    monkeypatch.setattr(service.api, "put_annotation", Mock(side_effect=put_annotation))
    command = CopyAnnotationMain(
        service,
        project_id="project1",
        all_yes=True,
        overwrite=True,
        merge=False,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    targets: list[CopyTarget] = [CopyTargetByInputData(src_task_id=f"src{index}", dest_task_id=f"dest{index}", src_input_data_id="input1", dest_input_data_id="input1") for index in range(101)]

    with caplog.at_level(logging.DEBUG):
        command.copy_annotations(targets, parallelism=2)

    assert len(copied) == 100
    assert "dest0" not in copied
    assert "dest100" in copied
    assert [len(task_ids) for task_ids in bulk_requests] == [100, 100, 2]
    assert "100 / 101" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and record.thread != main_thread_id for record in caplog.records)


class TestCopyAnnotation:
    def test_parse_copy_target__by_task(self):
        actual = parse_copy_target("task1:task2")
        assert isinstance(actual, CopyTargetByTask)
        assert actual.src_task_id == "task1"
        assert actual.dest_task_id == "task2"

    def test_parse_copy_target__by_input_data(self):
        actual = parse_copy_target("task1/input5:task2/input6")
        assert isinstance(actual, CopyTargetByInputData)
        assert actual.src_task_id == "task1"
        assert actual.src_input_data_id == "input5"
        assert actual.dest_task_id == "task2"
        assert actual.dest_input_data_id == "input6"

    def test_parse_copy_target__not_supported(self):
        with pytest.raises(ValueError):
            parse_copy_target("task1/input5:task2")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2/input6")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2:task3")

        with pytest.raises(ValueError):
            parse_copy_target("task1")
