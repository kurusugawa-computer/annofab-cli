from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole

from annofabcli import __main__
from annofabcli.__main__ import mask_sensitive_value_in_argv
from annofabcli.common.exceptions import ProjectAuthorizationError
from annofabcli.task import reject_tasks, reject_tasks_with_inspection_comments


def test__mask_sensitive_value_in_argv__password():
    actual = mask_sensitive_value_in_argv(["--annofab_user_id", "alice", "--annofab_password", "pw"])
    assert actual == ["--annofab_user_id", "***", "--annofab_password", "***"]


def test__mask_sensitive_value_in_argv__同じ引数を指定する():
    actual = mask_sensitive_value_in_argv(["--annofab_user_id", "alice", "--annofab_password", "pw_alice", "--annofab_user_id", "bob", "--annofab_password", "pw_bob"])
    assert actual == ["--annofab_user_id", "***", "--annofab_password", "***", "--annofab_user_id", "***", "--annofab_password", "***"]


def test__mask_sensitive_value_in_argv__pat():
    actual = mask_sensitive_value_in_argv(["--annofab_pat", "token"])
    assert actual == ["--annofab_pat", "***"]


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        (reject_tasks, ["task", "reject", "--project_id", "project1", "--task_id", "task1", "--comment", "要確認", "--cancel_acceptance", "--yes"]),
        (
            reject_tasks_with_inspection_comments,
            ["task", "reject_with_inspection_comments", "--project_id", "project1", "--json", '[{"task_id":"task1"}]', "--cancel_acceptance", "--yes"],
        ),
    ],
)
def test_rejectの受入取消権限エラーは理由を一度だけ表示する(command, arguments, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    facade = Mock()
    facade.validate_project.side_effect = ProjectAuthorizationError("テストプロジェクト", [ProjectMemberRole.OWNER])
    monkeypatch.setattr(command, "build_annofabapi_resource_and_login", Mock())
    monkeypatch.setattr(command, "AnnofabApiFacade", Mock(return_value=facade))
    monkeypatch.setattr(__main__.annofabcli.common.cli, "load_logging_config_from_args", Mock())

    if command is reject_tasks_with_inspection_comments:
        monkeypatch.setattr(command, "convert_cli_inspection_comment_list", Mock(return_value={"task1": {}}))

    with pytest.raises(SystemExit) as exc_info:
        __main__.main(arguments)

    assert exc_info.value.code == 1
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    assert "--cancel_acceptance" in error_records[0].getMessage()
    assert "オーナーロールが必要" in error_records[0].getMessage()
    assert error_records[0].exc_info is None
