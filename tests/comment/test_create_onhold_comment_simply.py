import argparse
from unittest.mock import Mock

import pytest
from annofabapi.models import CommentType

from annofabcli.__main__ import create_parser
from annofabcli.comment.create_onhold_comment_simply import CreateOnholdCommentSimply


def test_create_onhold_simply_parser() -> None:
    parser = create_parser()

    args = parser.parse_args(
        [
            "comment",
            "create_onhold_simply",
            "--project_id",
            "project1",
            "--task_id",
            "task1",
            "task2",
            "--comment",
            "コメント1",
            "--yes",
        ]
    )

    assert args.subcommand_name == "create_onhold_simply"
    assert args.project_id == "project1"
    assert args.task_id == ["task1", "task2"]
    assert args.comment == "コメント1"


def test_create_onhold_simply_puts_onhold_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    facade = Mock()
    put_comment_main = Mock()
    put_comment_main_class = Mock(return_value=put_comment_main)
    monkeypatch.setattr("annofabcli.comment.create_onhold_comment_simply.PutCommentSimplyMain", put_comment_main_class)

    args = argparse.Namespace(
        project_id="project1",
        task_id=["task1", "task2"],
        comment="コメント1",
        parallelism=4,
        yes=True,
    )

    CreateOnholdCommentSimply(service, facade, args).main()

    facade.validate_project.assert_called_once_with(project_id="project1", project_member_roles=None, organization_member_roles=None)
    put_comment_main_class.assert_called_once_with(service, project_id="project1", comment_type=CommentType.ONHOLD, all_yes=True)
    put_comment_main.put_comment_for_task_list.assert_called_once()
    _, kwargs = put_comment_main.put_comment_for_task_list.call_args
    assert kwargs["task_ids"] == ["task1", "task2"]
    assert kwargs["comment_info"].comment == "コメント1"
    assert kwargs["comment_info"].data is None
    assert kwargs["comment_info"].phrases is None
    assert kwargs["parallelism"] == 4
