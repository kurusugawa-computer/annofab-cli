import argparse
import logging
import threading
from unittest.mock import Mock

import pytest
import requests
from annofabapi.models import ProjectMemberRole, ProjectStatus

from annofabcli.__main__ import main
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.project import change_project_status
from annofabcli.project.change_project_status import ChanegProjectStatusMain, ChangeProjectStatus


@pytest.fixture
def service():
    service = Mock()
    service.wrapper.get_project_or_none.side_effect = lambda project_id: {
        "project_id": project_id,
        "title": project_id,
        "project_status": "active",
        "updated_datetime": "2026-01-01T00:00:00Z",
    }
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    return service


@pytest.mark.parametrize(("status", "force_suspend"), [(ProjectStatus.ACTIVE, False), (ProjectStatus.SUSPENDED, False), (ProjectStatus.SUSPENDED, True)])
def test_parallel_status_changes_preserve_options_skips_logs_and_unique_ids(service, caplog: pytest.LogCaptureFixture, status: ProjectStatus, *, force_suspend: bool) -> None:
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    looked_up: list[str] = []
    updated: list[str] = []
    original_lookup = service.wrapper.get_project_or_none.side_effect

    def get_project(project_id):
        assert threading.get_ident() != main_thread_id
        looked_up.append(project_id)
        return None if project_id == "missing" else original_lookup(project_id)

    def get_member(project_id):
        role = ProjectMemberRole.WORKER if project_id == "forbidden" else ProjectMemberRole.OWNER
        return {"member_role": role.value}, None

    def put_project(project_id, *, request_body):
        assert request_body["status"] == status.value
        assert request_body["force_suspend"] is force_suspend
        assert request_body["last_updated_datetime"] == "2026-01-01T00:00:00Z"
        if project_id in {"project1", "conflict"}:
            barrier.wait(timeout=10)
        if project_id == "conflict":
            response = requests.Response()
            response.status_code = 409
            raise requests.HTTPError(response=response)
        updated.append(project_id)
        return {}, None

    service.wrapper.get_project_or_none.side_effect = get_project
    service.api.get_my_member_in_project.side_effect = get_member
    service.api.put_project.side_effect = put_project
    args = argparse.Namespace(
        yes=True,
        project_id=["project1", "conflict", "missing", "forbidden", "project2", "project1"],
        status=status.value,
        suspend_with_working_tasks=force_suspend,
        parallelism=2,
    )

    with caplog.at_level(logging.DEBUG):
        ChangeProjectStatus(service, Mock(), args).main()

    assert sorted(updated) == ["project1", "project2"]
    assert sorted(looked_up) == ["conflict", "forbidden", "missing", "project1", "project2"]
    assert "成功: 2件, スキップ: 3件, 失敗: 0件" in caplog.messages[-1]
    assert "5 / 5 件のプロジェクトのステータス変更を処理しました。" in caplog.messages
    assert any(record.exc_info and "project_id='conflict'" in record.message for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and record.thread != main_thread_id for record in caplog.records)


@pytest.mark.parametrize("failed_api", ["read", "role", "write"])
def test_parallel_status_changes_wait_for_other_projects_before_reporting_failure(service, caplog: pytest.LogCaptureFixture, failed_api: str) -> None:
    original_lookup = service.wrapper.get_project_or_none.side_effect
    barrier = threading.Barrier(2)
    updated: list[str] = []

    def fail_if_needed(project_id: str, api: str) -> None:
        if project_id == "failed" and api == failed_api:
            response = requests.Response()
            response.status_code = 500
            raise requests.HTTPError(response=response)

    def get_project(project_id):
        fail_if_needed(project_id, "read")
        return original_lookup(project_id)

    def get_member(project_id):
        fail_if_needed(project_id, "role")
        return {"member_role": ProjectMemberRole.OWNER.value}, None

    def put_project(project_id, *, request_body):
        fail_if_needed(project_id, "write")
        assert request_body["status"] == "active"
        barrier.wait(timeout=10)
        updated.append(project_id)
        return {}, None

    service.wrapper.get_project_or_none.side_effect = get_project
    service.api.get_my_member_in_project.side_effect = get_member
    service.api.put_project.side_effect = put_project

    with caplog.at_level(logging.INFO), pytest.raises(AnnofabCliException):
        ChanegProjectStatusMain(service).change_status_for_project_list(["failed", "project1", "project2"], ProjectStatus.ACTIVE, parallelism=2)

    assert sorted(updated) == ["project1", "project2"]
    assert "成功: 2件, スキップ: 0件, 失敗: 1件" in caplog.messages[-1]
    assert any(record.exc_info and "project_id='failed'" in record.message for record in caplog.records)


@pytest.mark.parametrize("error", [requests.HTTPError(), requests.ConnectionError(), RuntimeError()])
def test_parallel_status_changes_report_errors_without_http_response(service, error: Exception) -> None:
    service.api.put_project.side_effect = error

    with pytest.raises(AnnofabCliException):
        ChanegProjectStatusMain(service).change_status_for_project_list(["failed"], ProjectStatus.ACTIVE, parallelism=2)


@pytest.mark.parametrize("status_code", [409, 500])
def test_sequential_status_changes_keep_existing_conflict_and_error_handling(service, status_code: int) -> None:
    updated: list[str] = []
    main_thread_id = threading.get_ident()

    def put_project(project_id, *, request_body):
        assert threading.get_ident() == main_thread_id
        assert request_body["status"] == "active"
        if project_id == "failed":
            response = requests.Response()
            response.status_code = status_code
            raise requests.HTTPError(response=response)
        updated.append(project_id)
        return {}, None

    service.api.put_project.side_effect = put_project
    command = ChanegProjectStatusMain(service)
    if status_code == 409:
        command.change_status_for_project_list(["failed", "project1"], ProjectStatus.ACTIVE)
        assert updated == ["project1"]
    else:
        with pytest.raises(requests.HTTPError):
            command.change_status_for_project_list(["failed", "project1"], ProjectStatus.ACTIVE)
        assert updated == []


@pytest.mark.parametrize("status_code", [409, 500])
def test_parallel_status_cli_reports_failure_only_after_other_projects_finish(service, monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    updated: list[str] = []

    def put_project(project_id, *, request_body):
        assert request_body["status"] == "active"
        if project_id == "failed":
            response = requests.Response()
            response.status_code = status_code
            raise requests.HTTPError(response=response)
        updated.append(project_id)
        return {}, None

    service.api.put_project.side_effect = put_project
    monkeypatch.setattr(change_project_status, "build_annofabapi_resource_and_login", Mock(return_value=service))
    arguments = ["project", "change_status", "--project_id", "failed", "project1", "--status", "active", "--parallelism", "2", "--disable_log"]

    if status_code == 409:
        main(arguments)
    else:
        with pytest.raises(SystemExit) as exc_info:
            main(arguments)
        assert exc_info.value.code == 1
    assert updated == ["project1"]
