from __future__ import annotations

import argparse
from unittest.mock import Mock

import pytest
from annofabapi.models import TaskPhase

from annofabcli.task import complete_tasks


def create_task_dict(*, status: str = "not_started", phase: str = "annotation") -> dict[str, object]:
    return {
        "project_id": "project1",
        "task_id": "task1",
        "phase": phase,
        "phase_stage": 1,
        "status": status,
        "input_data_id_list": ["input_data1"],
        "account_id": "account1",
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2024-01-01T00:00:00+00:00",
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": {},
    }


def test_complete_task_skips_on_hold_task_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="on_hold")
    main_obj = complete_tasks.CompleteTasksMain(service, all_yes=True)
    complete_task_mock = Mock(return_value=True)
    monkeypatch.setattr(main_obj, "complete_task_for_annotation_phase", complete_task_mock)

    result = main_obj.complete_task(
        project_id="project1",
        task_id="task1",
        target_phase=TaskPhase.ANNOTATION,
        target_phase_stage=1,
    )

    assert result is False
    complete_task_mock.assert_not_called()


def test_complete_task_allows_on_hold_task_when_option_is_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="on_hold")
    main_obj = complete_tasks.CompleteTasksMain(service, all_yes=True, include_on_hold_task=True)
    complete_task_mock = Mock(return_value=True)
    monkeypatch.setattr(main_obj, "complete_task_for_annotation_phase", complete_task_mock)

    result = main_obj.complete_task(
        project_id="project1",
        task_id="task1",
        target_phase=TaskPhase.ANNOTATION,
        target_phase_stage=1,
    )

    assert result is True
    complete_task_mock.assert_called_once()


def test_main_passes_include_on_hold_task_to_main_object(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    facade = Mock()
    args = argparse.Namespace(
        project_id="project1",
        task_id=["task1"],
        phase="annotation",
        phase_stage=1,
        inspection_status=None,
        reply_comment=None,
        task_query=None,
        parallelism=None,
        include_on_hold_task=True,
        yes=True,
    )

    complete_task_list_mock = Mock()
    complete_tasks_main_init_mock = Mock()

    class CompleteTasksMainStub:
        def __init__(self, _service, *, all_yes, include_on_hold_task):
            complete_tasks_main_init_mock(all_yes=all_yes, include_on_hold_task=include_on_hold_task)

        def complete_task_list(self, *args, **kwargs):
            complete_task_list_mock(*args, **kwargs)

    monkeypatch.setattr(complete_tasks, "CompleteTasksMain", CompleteTasksMainStub)
    monkeypatch.setattr(complete_tasks.annofabcli.common.cli, "get_list_from_args", lambda value: value)
    monkeypatch.setattr(complete_tasks.annofabcli.common.cli, "get_json_from_args", lambda _value: None)

    command = complete_tasks.CompleteTasks(service, facade, args)
    monkeypatch.setattr(command, "validate_project", Mock())

    command.main()

    complete_tasks_main_init_mock.assert_called_once_with(all_yes=True, include_on_hold_task=True)
    complete_task_list_mock.assert_called_once()
    assert complete_task_list_mock.call_args.args[0] == "project1"
    assert complete_task_list_mock.call_args.kwargs["target_phase"] == TaskPhase.ANNOTATION
