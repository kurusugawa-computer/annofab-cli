import threading
from unittest.mock import Mock

import pytest


@pytest.fixture
def threaded_comment_service() -> tuple[Mock, list[tuple[str, str]]]:
    service = Mock()
    service.api.account_id = "account1"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    barrier = threading.Barrier(2)
    main_thread_id = threading.get_ident()
    events: list[tuple[str, str]] = []

    def get_task(_project_id: str, task_id: str) -> dict | None:
        assert threading.get_ident() != main_thread_id
        if task_id == "missing":
            return None
        return {
            "task_id": task_id,
            "status": "not_started",
            "phase": "inspection",
            "phase_stage": 1,
            "account_id": "account1",
            "input_data_id_list": ["input1"],
        }

    def working(project_id, task_id):
        events.append((task_id, "working"))
        task = get_task(project_id, task_id)
        assert task is not None
        return {**task, "status": "working"}

    def update_comments(_project_id, task_id, _input_data_id, *, request_body):
        assert request_body
        events.append((task_id, "comment"))
        barrier.wait(timeout=10)
        if task_id == "task2":
            raise RuntimeError("comment API failure")
        return {}, None

    def pause(_project_id, task_id):
        events.append((task_id, "break"))

    service.wrapper.get_task_or_none.side_effect = get_task
    service.wrapper.change_task_status_to_working.side_effect = working
    service.wrapper.change_task_status_to_break.side_effect = pause
    service.api.batch_update_comments.side_effect = update_comments
    return service, events
