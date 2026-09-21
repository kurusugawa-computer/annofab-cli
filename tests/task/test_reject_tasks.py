import argparse
from unittest.mock import Mock, call

import pytest

from annofabcli.task import reject_tasks


def create_args(**kwargs) -> argparse.Namespace:
    defaults = {
        "project_id": "project1",
        "task_id": ["task1"],
        "yes": True,
        "parallelism": None,
        "not_assign": False,
        "assigned_annotator_user_id": None,
        "cancel_acceptance": False,
        "include_break_task": False,
        "include_on_hold_task": False,
        "comment": None,
        "task_query": None,
        "comment_data": None,
        "custom_project_type": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_reject_task_with_adding_comment_uses_assigned_account_id_without_re_resolving(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "status": "not_started",
        "phase": "acceptance",
        "updated_datetime": "2024-01-01T00:00:00+00:00",
    }
    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)
    monkeypatch.setattr(main_obj, "_can_reject_task", Mock(return_value=True))

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        assign_last_annotator=False,
        assigned_annotator=reject_tasks.AssignedAnnotator(account_id="account1", user_id="alice"),
    )

    assert result is True
    service.wrapper.reject_task.assert_called_once_with("project1", "task1", force=True, last_updated_datetime="2024-01-01T00:00:00+00:00")
    service.wrapper.change_task_operator.assert_called_once_with("project1", "task1", operator_account_id="account1")


def test_reject_task_restores_original_operator_when_adding_inspection_comment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.account_id = "executor-account"
    task = create_task_dict()
    task["account_id"] = "original-account"
    working_task = {**task, "account_id": "executor-account", "status": "working", "updated_datetime": "2024-01-01T00:01:00+00:00"}
    service.wrapper.get_task_or_none.return_value = task
    service.wrapper.change_task_operator.return_value = {**task, "account_id": "executor-account"}
    service.wrapper.change_task_status_to_working.return_value = working_task
    service.api.get_task.return_value = (working_task, None)

    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)
    monkeypatch.setattr(main_obj, "add_inspection_comment", Mock(side_effect=ValueError()))

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        inspection_comment="確認してください",
    )

    assert result is False
    assert service.wrapper.change_task_operator.call_args_list == [
        call("project1", "task1", operator_account_id="executor-account", last_updated_datetime="2024-01-01T00:00:00+00:00"),
        call("project1", "task1", operator_account_id="original-account"),
    ]


def test_main_resolves_assigned_annotator_user_id_before_reject_task_list(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    facade = Mock()
    args = create_args(assigned_annotator_user_id="alice")

    project_member_repository = Mock()
    project_member_repository.get_account_id_from_user_id.return_value = "account1"
    monkeypatch.setattr(reject_tasks, "ProjectMemberRepository", lambda _service: project_member_repository)

    reject_task_list_mock = Mock()

    class RejectTasksMainStub:
        def __init__(self, _service, *, comment_data, all_yes):
            self.comment_data = comment_data
            self.all_yes = all_yes

        def reject_task_list(self, *args, **kwargs):
            reject_task_list_mock(*args, **kwargs)

    monkeypatch.setattr(reject_tasks, "RejectTasksMain", RejectTasksMainStub)

    command = reject_tasks.RejectTasks(service, facade, args)
    command.main()

    reject_task_list_mock.assert_called_once()
    assert reject_task_list_mock.call_args.kwargs["assigned_annotator"] == reject_tasks.AssignedAnnotator(account_id="account1", user_id="alice")
    assert reject_task_list_mock.call_args.kwargs["assign_last_annotator"] is False


def test_main_rounds_image_comment_coordinates(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    facade = Mock()
    args = create_args(comment="コメント1", comment_data='{"x": 1.4, "y": 2.6, "_type": "Point"}')
    reject_task_list_mock = Mock()
    instances = []

    class RejectTasksMainStub:
        def __init__(self, _service, *, comment_data, all_yes):
            self.comment_data = comment_data
            self.all_yes = all_yes
            instances.append(self)

        def reject_task_list(self, *args, **kwargs):
            reject_task_list_mock(*args, **kwargs)

    monkeypatch.setattr(reject_tasks, "RejectTasksMain", RejectTasksMainStub)

    command = reject_tasks.RejectTasks(service, facade, args)
    command.main()

    assert reject_task_list_mock.call_args.kwargs["inspection_comment"] == "コメント1"
    assert instances[0].comment_data == {"x": 1, "y": 3, "_type": "Point"}


def test_main_stops_when_assigned_annotator_user_id_is_not_project_member(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    facade = Mock()
    args = create_args(assigned_annotator_user_id="alice")

    project_member_repository = Mock()
    project_member_repository.get_account_id_from_user_id.side_effect = ValueError("not found")
    monkeypatch.setattr(reject_tasks, "ProjectMemberRepository", lambda _service: project_member_repository)

    reject_task_list_mock = Mock()

    class RejectTasksMainStub:
        def __init__(self, _service, *, comment_data, all_yes):
            self.comment_data = comment_data
            self.all_yes = all_yes

        def reject_task_list(self, *args, **kwargs):
            reject_task_list_mock(*args, **kwargs)

    monkeypatch.setattr(reject_tasks, "RejectTasksMain", RejectTasksMainStub)

    command = reject_tasks.RejectTasks(service, facade, args)
    command.main()

    reject_task_list_mock.assert_not_called()


def create_task_dict(*, status: str = "not_started", phase: str = "acceptance") -> dict:
    return {
        "project_id": "project1",
        "task_id": "task1",
        "status": status,
        "phase": phase,
        "phase_stage": 1,
        "updated_datetime": "2024-01-01T00:00:00+00:00",
        "input_data_id_list": ["input1"],
        "account_id": "account1",
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": {},
    }


def test_reject_task_skips_on_hold_task_by_default() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="on_hold")
    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        assign_last_annotator=True,
        assigned_annotator=None,
    )

    assert result is False
    service.wrapper.reject_task.assert_not_called()


def test_reject_task_skips_break_task_by_default() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="break")
    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        assign_last_annotator=True,
        assigned_annotator=None,
    )

    assert result is False
    service.wrapper.reject_task.assert_not_called()


def test_reject_task_allows_break_task_when_option_is_enabled() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="break")
    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        assign_last_annotator=True,
        assigned_annotator=None,
        include_break_task=True,
    )

    assert result is True
    service.wrapper.reject_task.assert_called_once()


def test_reject_task_allows_on_hold_task_when_option_is_enabled() -> None:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = create_task_dict(status="on_hold")
    main_obj = reject_tasks.RejectTasksMain(service, comment_data=None, all_yes=True)

    result = main_obj.reject_task_with_adding_comment(
        project_id="project1",
        task_id="task1",
        assign_last_annotator=True,
        assigned_annotator=None,
        include_on_hold_task=True,
    )

    assert result is True
    service.wrapper.reject_task.assert_called_once()
