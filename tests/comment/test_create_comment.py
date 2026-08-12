from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from annofabapi.models import CommentType

from annofabcli.comment.put_comment import (
    AddedComment,
    PutCommentMain,
    convert_cli_inspection_comment_list,
    convert_cli_onhold_comment_list,
    read_inspection_comment_csv,
    read_onhold_comment_csv,
)
from annofabcli.comment.put_comment_simply import AddedSimpleComment, PutCommentSimplyMain


def test_convert_cli_inspection_comment_list() -> None:
    comments = convert_cli_inspection_comment_list(
        [
            {
                "task_id": "task1",
                "input_data_id": "input1",
                "comment": "コメント1",
                "data": {"x": 10, "y": 20, "_type": "Point"},
                "annotation_id": "annotation1",
                "phrases": ["phrase1"],
                "comment_id": "comment1",
            }
        ]
    )

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.data == {"x": 10, "y": 20, "_type": "Point"}
    assert comment.annotation_id == "annotation1"
    assert comment.phrases == ["phrase1"]
    assert comment.comment_id == "comment1"


def test_convert_cli_onhold_comment_list() -> None:
    comments = convert_cli_onhold_comment_list(
        [
            {
                "task_id": "task1",
                "input_data_id": "input1",
                "comment": "コメント1",
                "annotation_id": "annotation1",
                "comment_id": "comment1",
            }
        ]
    )

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.annotation_id == "annotation1"
    assert comment.comment_id == "comment1"


def test_add_comments_for_task_cancels_acceptance_before_creating_inspection_comment() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.api.get_comments.return_value = ([], None)
    service.api.get_editor_annotation.return_value = ({"details": []}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:00:00+00:00",
    }
    canceled_task = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "not_started",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:01:00+00:00",
    }
    events: list[str] = []

    def cancel_acceptance(*_: object, **__: object) -> dict[str, object]:
        events.append("cancel_acceptance")
        return canceled_task

    service.wrapper.cancel_completed_task.side_effect = cancel_acceptance
    service.wrapper.change_task_status_to_working.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "working",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "executor_account",
        "updated_datetime": "2024-01-01T00:02:00+00:00",
    }

    def confirm_processing(_: str) -> bool:
        events.append("confirm")
        return True

    main_obj = PutCommentMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=False)
    with patch.object(main_obj, "confirm_processing", side_effect=confirm_processing):
        result = main_obj.add_comments_for_task(
            task_id="task1",
            comments_for_task={"input1": [AddedComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"})]},
            put_mode="create",
            cancel_acceptance=True,
        )

    assert result == (1, 1)
    service.wrapper.cancel_completed_task.assert_called_once_with(
        "project1",
        "task1",
        operator_account_id="acceptor_account",
        last_updated_datetime="2024-01-01T00:00:00+00:00",
    )
    service.api.batch_update_comments.assert_called_once()
    service.wrapper.change_task_operator.assert_any_call("project1", "task1", "executor_account")
    service.wrapper.change_task_operator.assert_any_call("project1", "task1", "acceptor_account")
    assert events == ["confirm", "cancel_acceptance"]


def test_add_comments_for_task_does_not_cancel_acceptance_when_confirm_declined() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:00:00+00:00",
    }

    main_obj = PutCommentMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=False)
    with patch.object(main_obj, "confirm_processing", return_value=False):
        result = main_obj.add_comments_for_task(
            task_id="task1",
            comments_for_task={"input1": [AddedComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"})]},
            put_mode="create",
            cancel_acceptance=True,
        )

    assert result == (0, 0)
    service.wrapper.cancel_completed_task.assert_not_called()
    service.api.batch_update_comments.assert_not_called()


def test_add_comments_for_task_skips_when_not_assigned_to_me_and_change_operator_to_me_is_not_specified() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "not_started",
        "phase": "inspection",
        "account_id": "other_account",
    }

    main_obj = PutCommentMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=True)
    result = main_obj.add_comments_for_task(
        task_id="task1",
        comments_for_task={"input1": [AddedComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"})]},
        put_mode="create",
        change_operator_to_me=False,
    )

    assert result == (0, 0)
    service.wrapper.change_task_operator.assert_not_called()
    service.wrapper.change_task_status_to_working.assert_not_called()


def test_put_comment_for_task_skips_when_not_assigned_to_me_and_change_operator_to_me_is_not_specified() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "not_started",
        "phase": "inspection",
        "account_id": "other_account",
    }

    main_obj = PutCommentSimplyMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=True)
    result = main_obj.put_comment_for_task(
        task_id="task1",
        comment_info=AddedSimpleComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"}),
        change_operator_to_me=False,
    )

    assert result is False
    service.wrapper.change_task_operator.assert_not_called()
    service.wrapper.change_task_status_to_working.assert_not_called()


@pytest.mark.parametrize(
    "task_status",
    [
        "break",
        "on_hold",
    ],
)
def test_add_comments_for_task_skips_break_or_on_hold_task_by_default(task_status: str) -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": task_status,
        "phase": "inspection",
        "account_id": "executor_account",
    }

    main_obj = PutCommentMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=True)
    result = main_obj.add_comments_for_task(
        task_id="task1",
        comments_for_task={"input1": [AddedComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"})]},
        put_mode="create",
        include_break_task=False,
        include_on_hold_task=False,
    )

    assert result == (0, 0)
    service.wrapper.change_task_status_to_working.assert_not_called()


def test_add_comments_for_task_skips_onhold_comment_when_not_assigned_to_me_and_change_operator_to_me_is_not_specified() -> None:
    service = Mock()
    service.api.account_id = "account1"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "not_started",
        "phase": "annotation",
        "account_id": "other_account",
    }

    main_obj = PutCommentMain(service, project_id="project1", comment_type=CommentType.ONHOLD, all_yes=True)
    result = main_obj.add_comments_for_task(
        task_id="task1",
        comments_for_task={"input1": [AddedComment(comment="コメント1")]},
        put_mode="create",
        change_operator_to_me=False,
    )

    assert result == (0, 0)
    service.wrapper.change_task_operator.assert_not_called()


def test_put_comment_for_task_cancels_acceptance_before_creating_simple_inspection_comment() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:00:00+00:00",
    }
    canceled_task = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "not_started",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:01:00+00:00",
    }
    events: list[str] = []

    def cancel_acceptance(*_: object, **__: object) -> dict[str, object]:
        events.append("cancel_acceptance")
        return canceled_task

    service.wrapper.cancel_completed_task.side_effect = cancel_acceptance
    service.wrapper.change_task_status_to_working.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "working",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "executor_account",
        "updated_datetime": "2024-01-01T00:02:00+00:00",
    }

    def confirm_processing(_: str) -> bool:
        events.append("confirm")
        return True

    main_obj = PutCommentSimplyMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=False)
    with patch.object(main_obj, "confirm_processing", side_effect=confirm_processing):
        result = main_obj.put_comment_for_task(
            task_id="task1",
            comment_info=AddedSimpleComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"}),
            cancel_acceptance=True,
        )

    assert result is True
    service.wrapper.cancel_completed_task.assert_called_once_with(
        "project1",
        "task1",
        operator_account_id="acceptor_account",
        last_updated_datetime="2024-01-01T00:00:00+00:00",
    )
    service.api.batch_update_comments.assert_called_once()
    service.wrapper.change_task_operator.assert_any_call("project1", "task1", "executor_account")
    service.wrapper.change_task_operator.assert_any_call("project1", "task1", "acceptor_account")
    assert events == ["confirm", "cancel_acceptance"]


def test_put_comment_for_task_does_not_cancel_acceptance_when_confirm_declined() -> None:
    service = Mock()
    service.api.account_id = "executor_account"
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "input_data_id_list": ["input1"],
        "status": "complete",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "acceptor_account",
        "updated_datetime": "2024-01-01T00:00:00+00:00",
    }

    main_obj = PutCommentSimplyMain(service, project_id="project1", comment_type=CommentType.INSPECTION, all_yes=False)
    with patch.object(main_obj, "confirm_processing", return_value=False):
        result = main_obj.put_comment_for_task(
            task_id="task1",
            comment_info=AddedSimpleComment(comment="コメント1", data={"x": 10, "y": 20, "_type": "Point"}),
            cancel_acceptance=True,
        )

    assert result is False
    service.wrapper.cancel_completed_task.assert_not_called()
    service.api.batch_update_comments.assert_not_called()


def test_read_inspection_comment_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "inspection_comment.csv"
    csv_path.write_text('task_id,input_data_id,comment,data,annotation_id,phrases,comment_id\ntask1,input1,コメント1,"{""x"":10,""y"":20,""_type"":""Point""}",annotation1,"[""phrase1""]",comment1')

    comments = read_inspection_comment_csv(csv_path)

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.data == {"x": 10, "y": 20, "_type": "Point"}
    assert comment.annotation_id == "annotation1"
    assert comment.phrases == ["phrase1"]
    assert comment.comment_id == "comment1"


def test_read_onhold_comment_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "onhold_comment.csv"
    csv_path.write_text("task_id,input_data_id,comment,annotation_id,comment_id\ntask1,input1,コメント1,annotation1,comment1")

    comments = read_onhold_comment_csv(csv_path)

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.annotation_id == "annotation1"
    assert comment.comment_id == "comment1"
