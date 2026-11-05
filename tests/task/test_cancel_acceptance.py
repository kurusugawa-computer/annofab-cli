import logging
from threading import Barrier
from unittest.mock import Mock

import pytest

from annofabcli.task.cancel_acceptance import CancelAcceptanceMain


@pytest.mark.parametrize("assign_last_acceptor", [True, False])
@pytest.mark.parametrize("prefetch_fails", [True, False])
def test_thread_cancellation_reuses_members_and_recovers_from_prefetch_failure(caplog: pytest.LogCaptureFixture, *, assign_last_acceptor: bool, prefetch_fails: bool) -> None:
    service = Mock()
    barrier = Barrier(2)
    member_requests: list[str] = []
    cancellations: list[tuple[str, str | None]] = []

    def get_members(_project_id):
        member_requests.append("get_members")
        if prefetch_fails and len(member_requests) == 1:
            raise RuntimeError("members API failure")
        return [{"account_id": "account1", "user_id": "user1", "username": "member"}]

    def get_task(project_id, task_id):
        barrier.wait(timeout=10)
        return {
            "project_id": project_id,
            "task_id": task_id,
            "phase": "acceptance",
            "phase_stage": 1,
            "status": "complete",
            "input_data_id_list": ["input1"],
            "account_id": "account1",
            "histories_by_phase": [],
            "work_time_span": 0,
            "number_of_rejections": 0,
            "started_datetime": None,
            "updated_datetime": "2026-01-01T00:00:00Z",
            "operation_updated_datetime": None,
            "sampling": None,
            "metadata": {},
        }

    def cancel(_project_id, task_id, *, operator_account_id):
        cancellations.append((task_id, operator_account_id))

    service.wrapper.get_all_project_members.side_effect = get_members
    service.wrapper.get_task_or_none.side_effect = get_task
    service.wrapper.cancel_completed_task.side_effect = cancel
    main_obj = CancelAcceptanceMain(service, "project1", all_yes=True)

    with caplog.at_level(logging.INFO):
        main_obj.cancel_acceptance_for_task_list(["task1", "task2"], assign_last_acceptor=assign_last_acceptor, parallelism=2)

    expected_account_id = "account1" if assign_last_acceptor else None
    assert sorted(cancellations) == [("task1", expected_account_id), ("task2", expected_account_id)]
    if assign_last_acceptor and prefetch_fails:
        # 再取得後のキャッシュは共有する。同時に再取得を始めた場合は両スレッドが取得する。
        assert 2 <= len(member_requests) <= 3
    else:
        assert len(member_requests) == (1 if assign_last_acceptor else 0)
    assert "2 / 2" in caplog.messages[-1]
    for task_id in ["task1", "task2"]:
        assert f"task_id = '{task_id}' の受け入れ取り消しが成功しました。" in caplog.text
    if prefetch_fails and assign_last_acceptor:
        assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
