from annofabapi.models import TaskStatus

from annofabcli.statistics.summarize_task_count import SimpleTaskStatus, get_step_for_current_phase


class TestSimpleTaskStatus:
    def test_from_task_status(self):
        assert SimpleTaskStatus.from_task_status(TaskStatus.ON_HOLD) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.BREAK) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.WORKING) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.NOT_STARTED) == SimpleTaskStatus.NOT_STARTED
        assert SimpleTaskStatus.from_task_status(TaskStatus.COMPLETE) == SimpleTaskStatus.COMPLETE


def test_get_step_for_current_phase():
    task = {
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
        "account_id": "account1",
        "histories_by_phase": [{"account_id": "account1", "phase": "annotation", "phase_stage": 1, "worked": False}],
        "work_time_span": 0,
    }
    assert get_step_for_current_phase(task, number_of_inspections=1) == 1
