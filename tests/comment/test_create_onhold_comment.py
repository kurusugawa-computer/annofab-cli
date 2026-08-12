import argparse
from unittest.mock import Mock

import pytest
from annofabapi.models import CommentType, ProjectMemberRole

from annofabcli.comment.create_onhold_comment import CreateOnholdComment


def test_create_onhold_passes_task_status_options(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    facade = Mock()
    put_comment_main = Mock()
    put_comment_main_class = Mock(return_value=put_comment_main)
    monkeypatch.setattr("annofabcli.comment.create_onhold_comment.PutCommentMain", put_comment_main_class)
    monkeypatch.setattr(
        "annofabcli.comment.create_onhold_comment.annofabcli.common.cli.get_json_from_args",
        Mock(return_value=[{"task_id": "task1", "input_data_id": "input_data1", "comment": "コメント1"}]),
    )

    args = argparse.Namespace(
        project_id="project1",
        json="[]",
        csv=None,
        parallelism=4,
        change_operator_to_me=False,
        include_break_task=True,
        include_on_hold_task=True,
        yes=True,
    )

    CreateOnholdComment(service, facade, args).main()

    facade.validate_project.assert_called_once_with(
        project_id="project1",
        project_member_roles=[ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER, ProjectMemberRole.WORKER],
        organization_member_roles=None,
    )
    put_comment_main_class.assert_called_once_with(service, project_id="project1", comment_type=CommentType.ONHOLD, all_yes=True)
    put_comment_main.add_comments_for_task_list.assert_called_once()
    _, kwargs = put_comment_main.add_comments_for_task_list.call_args
    assert kwargs["parallelism"] == 4
    assert kwargs["put_mode"] == "create"
    assert kwargs["change_operator_to_me"] is False
    assert kwargs["include_break_task"] is True
    assert kwargs["include_on_hold_task"] is True
