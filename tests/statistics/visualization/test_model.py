import pytest
from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus

from annofabcli.statistics.visualization.model import TaskCompletionCriteria


@pytest.mark.parametrize(
    "task,criteria,expected",
    [
        # ACCEPTANCE_COMPLETED
        (
            {"phase": TaskPhase.ACCEPTANCE.value, "status": TaskStatus.COMPLETE.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
            True,
        ),
        (
            {"phase": TaskPhase.ACCEPTANCE.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
            False,
        ),
        (
            {"phase": TaskPhase.INSPECTION.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
            False,
        ),
        # ACCEPTANCE_REACHED
        (
            {"phase": TaskPhase.ACCEPTANCE.value, "status": TaskStatus.COMPLETE.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_REACHED,
            True,
        ),
        (
            {"phase": TaskPhase.ACCEPTANCE.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_REACHED,
            True,
        ),
        (
            {"phase": TaskPhase.INSPECTION.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.ACCEPTANCE_REACHED,
            False,
        ),
        # INSPECTION_REACHED
        (
            {"phase": TaskPhase.INSPECTION.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.INSPECTION_REACHED,
            True,
        ),
        (
            {"phase": TaskPhase.ACCEPTANCE.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.INSPECTION_REACHED,
            True,
        ),
        (
            {"phase": TaskPhase.ANNOTATION.value, "status": TaskStatus.NOT_STARTED.value, "work_time_span": 1},
            TaskCompletionCriteria.INSPECTION_REACHED,
            False,
        ),
    ],
)
def test_is_task_completed(task, criteria, expected):
    assert criteria.is_task_completed(task) == expected
