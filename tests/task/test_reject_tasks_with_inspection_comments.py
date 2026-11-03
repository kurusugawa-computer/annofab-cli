from threading import Barrier
from unittest.mock import Mock

from annofabcli.comment.put_comment import AddedComment
from annofabcli.task import reject_tasks_with_inspection_comments


def create_task_dict(*, status: str = "not_started") -> dict:
    return {
        "project_id": "project1",
        "task_id": "task1",
        "status": status,
        "phase": "inspection",
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


def test_reject_task_creates_inspection_comments_before_reject(monkeypatch) -> None:
    service = Mock()
    service.api.account_id = "account1"
    task = create_task_dict()
    working_task = {**task, "status": "working", "updated_datetime": "2024-01-01T00:01:00+00:00"}
    service.wrapper.get_task_or_none.return_value = task
    service.wrapper.change_task_status_to_working.return_value = working_task

    comment_main = Mock()
    monkeypatch.setattr(reject_tasks_with_inspection_comments, "PutCommentMain", Mock(return_value=comment_main))
    comments_for_task_list = {"task1": {"input1": [AddedComment(comment="確認してください", annotation_id="annotation1")]}}
    main_obj = reject_tasks_with_inspection_comments.RejectTasksWithInspectionCommentsMain(
        service,
        project_id="project1",
        comments_for_task_list=comments_for_task_list,
        all_yes=True,
    )

    result = main_obj.reject_task_with_adding_comment("project1", "task1", inspection_comment="")

    assert result is True
    comment_main.add_comments_to_working_task.assert_called_once_with(working_task, comments_for_task_list["task1"], put_mode="create")
    service.wrapper.reject_task.assert_called_once_with("project1", "task1", force=False, last_updated_datetime="2024-01-01T00:01:00+00:00")


def test_reject_task_does_not_reject_when_comment_creation_fails(monkeypatch) -> None:
    service = Mock()
    service.api.account_id = "account1"
    task = create_task_dict()
    working_task = {**task, "status": "working", "updated_datetime": "2024-01-01T00:01:00+00:00"}
    service.wrapper.get_task_or_none.return_value = task
    service.wrapper.change_task_status_to_working.return_value = working_task
    service.api.get_task.return_value = (working_task, None)

    comment_main = Mock()
    comment_main.add_comments_to_working_task.side_effect = ValueError()
    monkeypatch.setattr(reject_tasks_with_inspection_comments, "PutCommentMain", Mock(return_value=comment_main))
    comments_for_task_list = {"task1": {"input1": [AddedComment(comment="確認してください", annotation_id="annotation1")]}}
    main_obj = reject_tasks_with_inspection_comments.RejectTasksWithInspectionCommentsMain(
        service,
        project_id="project1",
        comments_for_task_list=comments_for_task_list,
        all_yes=True,
    )

    result = main_obj.reject_task_with_adding_comment("project1", "task1", inspection_comment="")

    assert result is False
    service.wrapper.reject_task.assert_not_called()
    service.wrapper.change_task_status_to_break.assert_called_once_with("project1", "task1", last_updated_datetime="2024-01-01T00:01:00+00:00")


def test_thread_reject_uses_target_comments_before_rejecting_each_task() -> None:
    service = Mock()
    service.api.account_id = "account1"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    barrier = Barrier(2)
    events: list[tuple[str, str]] = []
    comments = {task_id: {"input1": [AddedComment(comment=task_id)]} for task_id in ["task1", "task2"]}

    def get_task(_project_id, task_id):
        return {**create_task_dict(), "task_id": task_id}

    def working(_project_id, task_id, **_kwargs):
        return {**create_task_dict(status="working"), "task_id": task_id}

    def add_comments(_project_id, task_id, _input_data_id, *, request_body):
        barrier.wait(timeout=10)
        assert [comment["comment"] for comment in request_body] == [task_id]
        events.append((task_id, "comment"))
        return {}, None

    def reject(_project_id, task_id, **_kwargs):
        events.append((task_id, "reject"))

    service.wrapper.get_task_or_none.side_effect = get_task
    service.wrapper.change_task_status_to_working.side_effect = working
    service.api.batch_update_comments.side_effect = add_comments
    service.wrapper.reject_task.side_effect = reject
    main_obj = reject_tasks_with_inspection_comments.RejectTasksWithInspectionCommentsMain(service, project_id="project1", comments_for_task_list=comments, all_yes=True)

    main_obj.reject_task_list("project1", ["task1", "task2"], inspection_comment="", parallelism=2)

    for task_id in comments:
        assert [event for event_task_id, event in events if event_task_id == task_id] == ["comment", "reject"]
