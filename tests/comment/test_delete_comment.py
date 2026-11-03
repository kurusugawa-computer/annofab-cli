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
