from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from annofabcli.annotation.dump_annotation import DumpAnnotationMain


def test_thread_dump_preserves_batches_files_counts_and_worker_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_project.return_value = ({"title": "project"}, None)
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    bulk_requests: list[list[str]] = []

    def get_tasks(_project_id, *, query_params):
        task_ids = query_params["task_id"].split(",")
        bulk_requests.append(task_ids)
        return {"success": [{"task_id": task_id, "input_data_id_list": ["input1"]} for task_id in task_ids]}, None

    def get_annotation(_project_id, task_id, _input_data_id, *, query_params):
        assert threading.get_ident() != main_thread_id
        assert query_params["task_history_id"] == "history1"
        if task_id in {"task0", "task1"}:
            barrier.wait(timeout=10)
        if task_id == "task0":
            raise RuntimeError("annotation API failure")
        return {"format_version": "2.0.0", "details": [], "input_data_id": "input1", "task_id": task_id}, None

    service.api.get_tasks_in_bulk.side_effect = get_tasks
    service.api.get_editor_annotation.side_effect = get_annotation
    with caplog.at_level(logging.DEBUG):
        DumpAnnotationMain(service, "project1").dump_annotation([f"task{index}" for index in range(101)], tmp_path, task_history_id="history1", parallelism=2)

    assert bulk_requests == [[f"task{index}" for index in range(100)], ["task100"]]
    assert len(list(tmp_path.glob("*/input1.json"))) == 100
    assert json.loads((tmp_path / "task100/input1.json").read_text(encoding="utf-8"))["task_id"] == "task100"
    assert "100 / 101" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and record.thread != main_thread_id for record in caplog.records)


class TestDumpAnnotationMain:
    @pytest.mark.parametrize("format_version", [None, "1.0.0"])
    def test_dump_rejects_v1_without_writing_backup(self, tmp_path: Path, format_version: str | None) -> None:
        annotation: dict[str, Any] = {"details": []}
        if format_version is not None:
            annotation["format_version"] = format_version
        json_path = tmp_path / "input1.json"
        service = Mock()
        main_obj = DumpAnnotationMain(service, "prj1")

        with pytest.raises(ValueError):
            main_obj.dump_editor_annotation(annotation, json_path)

        assert not json_path.exists()
        service.wrapper.download.assert_not_called()

    @pytest.mark.parametrize("has_outer", [False, True])
    def test_dump_v2(self, tmp_path: Path, *, has_outer: bool) -> None:
        annotation: dict[str, Any] = {
            "format_version": "2.0.0",
            "input_data_id": "input1",
            "details": [{"annotation_id": "inner1", "body": {"_type": "Inner", "data": {"x": 1, "y": 2}}}],
        }
        if has_outer:
            annotation["details"].append({"annotation_id": "outer1", "body": {"_type": "Outer", "url": "https://example.com/outer1"}})
        json_path = tmp_path / "input1.json"
        service = Mock()
        outer_data = b'{"points":[1,2]}'

        def download(_url, dest_path):
            dest_path.write_bytes(outer_data)

        service.wrapper.download.side_effect = download
        main_obj = DumpAnnotationMain(service, "prj1")

        main_obj.dump_editor_annotation(annotation, json_path)

        json_text = json_path.read_text(encoding="utf-8")
        assert json.loads(json_text) == annotation
        assert json_text.startswith('{\n  "format_version": "2.0.0",\n')
        assert json_text.endswith("\n")
        if has_outer:
            assert (tmp_path / "input1" / "outer1").read_bytes() == outer_data
        else:
            assert not (tmp_path / "input1").exists()
            service.wrapper.download.assert_not_called()
