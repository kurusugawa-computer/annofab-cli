from unittest.mock import Mock

import pytest

from annofabcli import __main__
from annofabcli.__main__ import mask_sensitive_value_in_argv
from annofabcli.common.exceptions import AuthenticationError
from annofabcli.task import reject_tasks, reject_tasks_with_inspection_comments


@pytest.mark.parametrize("option", ["--annofab_user_id", "--annofab_password", "--annofab_pat"])
def test_mask_sensitive_equal_arguments(option: str) -> None:
    arguments = ["task", "list", f"{option}=first=second", option, "secret", f"{option}="]
    original = arguments.copy()
    assert mask_sensitive_value_in_argv(arguments) == ["task", "list", f"{option}=***", option, "***", f"{option}=***"]
    assert arguments == original


def test_mask_sensitive_argument_without_value() -> None:
    assert mask_sensitive_value_in_argv(["--annofab_password"]) == ["--annofab_password"]


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
    service = Mock()
    service.api.get_project.return_value = ({"title": "テストプロジェクト"}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": "accepter"}, None)
    monkeypatch.setattr(command, "build_annofabapi_resource_and_login", Mock(return_value=service))
    monkeypatch.setattr(__main__.annofabcli.common.cli, "load_logging_config_from_args", Mock())

    if command is reject_tasks_with_inspection_comments:
        monkeypatch.setattr(command, "convert_cli_inspection_comment_list", Mock(return_value={"task1": {}}))

    with pytest.raises(SystemExit) as exc_info:
        __main__.main(arguments)

    assert exc_info.value.code == 1
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    assert "--cancel_acceptance" in error_records[0].getMessage()
    assert "オーナーロール（owner）が必要" in error_records[0].getMessage()
    assert "テストプロジェクト" in error_records[0].getMessage()
    assert error_records[0].exc_info is None


@pytest.mark.parametrize(("error", "has_traceback"), [(AuthenticationError("alice"), False), (ValueError("unexpected"), True)])
def test_cliエラーは一度だけ表示する(error: Exception, has_traceback: bool, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:  # noqa: FBT001
    monkeypatch.setattr(reject_tasks, "build_annofabapi_resource_and_login", Mock(side_effect=error))
    monkeypatch.setattr(__main__.annofabcli.common.cli, "load_logging_config_from_args", Mock())

    with pytest.raises(SystemExit) as exc_info:
        __main__.main(["task", "reject", "--project_id", "project1", "--task_id", "task1"])

    assert exc_info.value.code == 1
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    assert (error_records[0].exc_info is not None) is has_traceback
