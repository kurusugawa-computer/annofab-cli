import logging
import threading
from unittest.mock import Mock

import pytest

from annofabcli.project.update_project import UpdatedProject, UpdateProjectMain


@pytest.mark.parametrize("failed_api", ["read", "write"])
def test_thread_update_preserves_result_counts_and_worker_logs(caplog: pytest.LogCaptureFixture, failed_api: str) -> None:
    service = Mock()
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    updated_project_ids: list[str] = []
    projects = {
        project_id: {
            "project_id": project_id,
            "title": "old_title",
            "overview": "old_overview",
            "project_status": "active",
            "updated_datetime": "2026-01-01T00:00:00Z",
        }
        for project_id in ["project1", "failed", "unchanged"]
    }

    def get_project(project_id):
        assert threading.get_ident() != main_thread_id
        if project_id in {"project1", "failed"}:
            barrier.wait(timeout=10)
        if project_id == "failed" and failed_api == "read":
            raise RuntimeError("read API failure")
        return projects.get(project_id)

    def put_project(project_id, *, request_body):
        assert request_body["title"] == "new_title"
        assert request_body["overview"] == "old_overview"
        assert request_body["status"] == "active"
        assert request_body["last_updated_datetime"] == "2026-01-01T00:00:00Z"
        if project_id == "failed":
            raise RuntimeError("write API failure")
        updated_project_ids.append(project_id)
        return {}, None

    service.wrapper.get_project_or_none.side_effect = get_project
    service.api.put_project.side_effect = put_project
    command = UpdateProjectMain(service, all_yes=True)
    updates = [UpdatedProject(project_id=project_id, title="new_title") for project_id in ["project1", "failed", "missing"]]
    updates.append(UpdatedProject(project_id="unchanged"))

    with caplog.at_level(logging.DEBUG):
        command.update_project_list_in_parallel(updates, parallelism=2)

    assert updated_project_ids == ["project1"]
    assert "成功: 1件, スキップ: 2件, 失敗: 1件" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "プロジェクトを更新しました" in record.message for record in caplog.records)
    assert all(project["title"] == "old_title" and "last_updated_datetime" not in project for project in projects.values())
