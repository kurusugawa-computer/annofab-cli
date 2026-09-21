from unittest.mock import Mock

import pytest

from annofabcli.task.change_status_to_on_hold import ChangingStatusToOnHoldMain


@pytest.mark.parametrize("task_account_id", ["other_account", None])
def test_change_status_to_on_hold_for_task_worker_skips_task_not_assigned_to_me(task_account_id: str | None) -> None:
    service = Mock()
    service.api.account_id = "my_account"
    service.wrapper.get_task_or_none.return_value = {
        "project_id": "project1",
        "task_id": "task1",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
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
    main_obj = ChangingStatusToOnHoldMain(service, project_id="project1", all_yes=True, can_operate_other_task=False)

    actual = main_obj.change_status_to_on_hold_for_task("task1")

    assert actual is False
    service.wrapper.change_task_operator.assert_not_called()
    service.wrapper.change_task_status_to_working.assert_not_called()
    service.wrapper.change_task_status_to_on_hold.assert_not_called()
