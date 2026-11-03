import logging

import pytest
from annofabapi.models import CommentType

from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain


@pytest.mark.parametrize("comment_type", [CommentType.INSPECTION, CommentType.ONHOLD])
def test_thread_simple_comments_preserve_counts_logs_and_status_order(threaded_comment_service, caplog: pytest.LogCaptureFixture, comment_type: CommentType) -> None:
    service, events = threaded_comment_service
    command = PutCommentSimplyMain(service, "project1", comment_type, all_yes=True)
    comment = AddedSimpleComment(comment="new", data=None)

    with caplog.at_level(logging.DEBUG):
        command.put_comment_for_task_list(["task1", "task2", "missing"], comment, parallelism=2)

    assert "1 / 3 件のタスクに" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "コメントを付与しました" in record.message for record in caplog.records)
    for task_id in ["task1", "task2"]:
        assert [event for event_task_id, event in events if event_task_id == task_id] == ["working", "comment", "break"]
