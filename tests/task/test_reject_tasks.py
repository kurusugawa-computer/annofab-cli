import argparse
from unittest.mock import Mock

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
        assigned_annotator_account_id="account1",
    )

    assert result is True
    service.wrapper.reject_task.assert_called_once_with("project1", "task1", force=True, last_updated_datetime="2024-01-01T00:00:00+00:00")
    service.wrapper.change_task_operator.assert_called_once_with("project1", "task1", operator_account_id="account1")


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
    assert reject_task_list_mock.call_args.kwargs["assigned_annotator_account_id"] == "account1"
    assert reject_task_list_mock.call_args.kwargs["assign_last_annotator"] is False


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
