import logging
from threading import Barrier
from unittest.mock import Mock

import pytest

from annofabcli.task.change_status_to_break import ChangeStatusToBreakMain


@pytest.mark.parametrize("task_account_id", ["other_account", None])
def test_change_status_to_break_for_task_worker_skips_task_not_assigned_to_me(task_account_id: str | None) -> None:
    service = Mock()
    service.api.account_id = "my_account"
    service.wrapper.get_task_or_none.return_value = {
        "project_id": "project1",
        "task_id": "task1",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "working",
        "input_data_id_list": ["input_data1"],
        "account_id": task_account_id,
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2024-01-01T00:00:00+00:00",
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": {},
    }
    main_obj = ChangeStatusToBreakMain(service, all_yes=True, can_operate_other_task=False)

    actual = main_obj.change_status_to_break_for_task("project1", "task1")

    assert actual is False
    service.wrapper.change_task_status_to_break.assert_not_called()
    service.wrapper.change_task_status_to_working.assert_not_called()


@pytest.mark.parametrize("first_update_fails", [False, True])
def test_thread_updates_preserve_status_order_skip_and_logs(caplog: pytest.LogCaptureFixture, *, first_update_fails: bool) -> None:
    service = Mock()
    barrier = Barrier(2)
    events: list[tuple[str, str]] = []
    updated: list[str] = []

    def get_task(project_id, task_id):
        if task_id != "complete":
            barrier.wait(timeout=10)
        return {
            "project_id": project_id,
            "task_id": task_id,
            "phase": "annotation",
            "phase_stage": 1,
            "status": {"task0": "on_hold", "task1": "working", "complete": "complete"}[task_id],
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

    def working(_project_id, task_id):
        events.append((task_id, "working"))

    def pause(_project_id, task_id):
        events.append((task_id, "break"))
        if first_update_fails and task_id == "task0":
            raise RuntimeError("status API failure")
        updated.append(task_id)

    service.wrapper.get_task_or_none.side_effect = get_task
    service.wrapper.change_task_status_to_working.side_effect = working
    service.wrapper.change_task_status_to_break.side_effect = pause
    main_obj = ChangeStatusToBreakMain(service, all_yes=True, can_operate_other_task=True)

    with caplog.at_level(logging.INFO):
        main_obj.change_status_to_break("project1", ["task0", "task1", "complete"], parallelism=2)

    assert [state for task_id, state in events if task_id == "task0"] == ["working", "break"]
    assert [state for task_id, state in events if task_id == "task1"] == ["break"]
    assert sorted(updated) == (["task1"] if first_update_fails else ["task0", "task1"])
    assert f"{len(updated)} / 3" in caplog.text
    if first_update_fails:
        assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
