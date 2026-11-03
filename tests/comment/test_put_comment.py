import logging

import pytest
from annofabapi.models import CommentType

from annofabcli.comment.put_comment import AddedComment, CommentPutMode, PutCommentMain


@pytest.mark.parametrize("comment_type", [CommentType.INSPECTION, CommentType.ONHOLD])
@pytest.mark.parametrize("put_mode", ["create", "put", "update"])
def test_thread_comments_preserve_counts_logs_and_status_order(threaded_comment_service, caplog: pytest.LogCaptureFixture, comment_type: CommentType, put_mode: CommentPutMode) -> None:
    service, events = threaded_comment_service
    service.api.get_comments.return_value = (
        [
            {
                "comment_id": comment_id,
                "comment_type": comment_type.value,
                "comment": "old",
                "comment_node": {"_type": "Root"},
            }
            for comment_id in ["comment1", "comment2"]
        ],
        None,
    )
    data = {"_type": "Point", "x": 0, "y": 0} if comment_type == CommentType.INSPECTION else None
    comments = [AddedComment(comment="new", data=data, comment_id=comment_id if put_mode == "update" else None) for comment_id in ["comment1", "comment2"]]
    comments_by_task = {"task1": {"input1": comments}, "task2": {"input1": comments[:1]}, "missing": {"input1": comments[:1]}}
    command = PutCommentMain(service, "project1", comment_type, all_yes=True)

    with caplog.at_level(logging.DEBUG):
        command.add_comments_for_task_list(comments_by_task, parallelism=2, put_mode=put_mode)

    assert "1 / 3 件のタスク, 1 / 3 件の入力データ, 2 / 4 件の" in caplog.messages[-1]
    assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)
    assert any(record.levelno == logging.DEBUG and "2件のコメントを付与しました" in record.message for record in caplog.records)
    for task_id in ["task1", "task2"]:
        assert [event for event_task_id, event in events if event_task_id == task_id] == ["working", "comment", "break"]


@pytest.mark.parametrize("failed_api", ["get_task_or_none", "change_task_status_to_working", "change_task_status_to_break"])
def test_thread_comments_continue_after_task_api_failure(threaded_comment_service, caplog: pytest.LogCaptureFixture, failed_api: str) -> None:
    service, events = threaded_comment_service
    service.api.batch_update_comments.side_effect = None
    failing_api = getattr(service.wrapper, failed_api)
    original_effect = failing_api.side_effect

    def fail_first(project_id, task_id):
        if task_id == "failed":
            raise RuntimeError("task API failure")
        return original_effect(project_id, task_id)

    failing_api.side_effect = fail_first
    command = PutCommentMain(service, "project1", CommentType.ONHOLD, all_yes=True)
    comments_by_task = {task_id: {"input1": [AddedComment(comment="new")]} for task_id in ["failed", "task1", "task3"]}

    with caplog.at_level(logging.INFO):
        command.add_comments_for_task_list(comments_by_task, parallelism=1, put_mode="create")

    assert "2 / 3 件のタスク, 2 / 3 件の入力データ, 2 / 3 件の" in caplog.messages[-1]
    assert any("task_id='failed'" in record.message and record.exc_info for record in caplog.records)
    assert ("task1", "break") in events
    assert ("task3", "break") in events
