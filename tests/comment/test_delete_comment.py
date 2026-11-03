import logging

import pytest

from annofabcli.comment.delete_comment import DeleteCommentMain


def test_thread_delete_preserves_counts_logs_and_status_order(threaded_comment_service, caplog: pytest.LogCaptureFixture) -> None:
    service, events = threaded_comment_service
    service.api.get_comments.return_value = ([{"comment_id": "comment1"}], None)
    command = DeleteCommentMain(service, "project1", all_yes=True)
    comments_by_task = {task_id: {"input1": ["comment1"]} for task_id in ["task1", "task2", "missing"]}

    with caplog.at_level(logging.DEBUG):
        command.delete_comments_for_task_list(comments_by_task, parallelism=2)

    assert "1 / 3 件の入力データからコメントを削除しました" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "1件のコメントを削除しました" in record.message for record in caplog.records)
    for task_id in ["task1", "task2"]:
        assert [event for event_task_id, event in events if event_task_id == task_id] == ["working", "comment", "break"]


@pytest.mark.parametrize("failed_api", ["get_task_or_none", "change_task_status_to_working", "change_task_status_to_break"])
def test_thread_delete_continues_after_task_api_failure(threaded_comment_service, caplog: pytest.LogCaptureFixture, failed_api: str) -> None:
    service, events = threaded_comment_service
    service.api.get_comments.return_value = ([{"comment_id": "comment1"}], None)
    service.api.batch_update_comments.side_effect = None
    failing_api = getattr(service.wrapper, failed_api)
    original_effect = failing_api.side_effect

    def fail_first(project_id, task_id):
        if task_id == "failed":
            raise RuntimeError("task API failure")
        return original_effect(project_id, task_id)

    failing_api.side_effect = fail_first
    command = DeleteCommentMain(service, "project1", all_yes=True)
    comments_by_task = {task_id: {"input1": ["comment1"]} for task_id in ["failed", "task1", "task3"]}

    with caplog.at_level(logging.INFO):
        command.delete_comments_for_task_list(comments_by_task, parallelism=1)

    assert "2 / 3 件の入力データからコメントを削除しました" in caplog.messages[-1]
    assert any("task_id='failed'" in record.message and record.exc_info for record in caplog.records)
    assert ("task1", "break") in events
    assert ("task3", "break") in events
