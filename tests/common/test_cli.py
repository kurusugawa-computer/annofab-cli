import argparse
import builtins
import logging

import pytest
from annofabapi.credentials import IdPass, Pat

from annofabcli.common.cli import (
    DEFAULT_ENDPOINT_URL,
    build_annofabapi_resource,
    get_endpoint_url,
    get_json_from_args,
    get_list_from_args,
    non_negative_int,
    positive_int,
    prompt_yesno,
    prompt_yesnoall,
)


@pytest.mark.parametrize("auth_source", ["command_line_pat", "environment_pat", "command_line_password", "command_line_user_stdin_password", "environment_password", "stdin"])
def test_build_annofabapi_resource(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, auth_source: str) -> None:
    for name in ("ANNOFAB_PAT", "ANNOFAB_USER_ID", "ANNOFAB_PASSWORD", "ANNOFAB_ENDPOINT_URL"):
        monkeypatch.delenv(name, raising=False)

    args = argparse.Namespace(endpoint_url=None, annofab_pat=None, annofab_user_id=None, annofab_password=None)
    expected_credentials: IdPass | Pat = IdPass("test-user", "test-password")
    if auth_source == "command_line_pat":
        args.annofab_pat = "command-line-token"
        monkeypatch.setenv("ANNOFAB_PAT", "environment-token")
        expected_credentials = Pat("command-line-token")
    elif auth_source == "environment_pat":
        monkeypatch.setenv("ANNOFAB_PAT", "environment-token")
        monkeypatch.setenv("ANNOFAB_USER_ID", "test-user")
        monkeypatch.setenv("ANNOFAB_PASSWORD", "test-password")
        expected_credentials = Pat("environment-token")
    elif auth_source == "command_line_password":
        args.annofab_user_id = "test-user"
        args.annofab_password = "test-password"
        monkeypatch.setenv("ANNOFAB_PAT", "environment-token")
    elif auth_source == "command_line_user_stdin_password":
        args.annofab_user_id = "test-user"
        monkeypatch.setattr("getpass.getpass", lambda _prompt: "test-password")
    elif auth_source == "environment_password":
        monkeypatch.setenv("ANNOFAB_USER_ID", "test-user")
        monkeypatch.setenv("ANNOFAB_PASSWORD", "test-password")
    else:
        monkeypatch.setattr(builtins, "input", lambda _prompt: "test-user")
        monkeypatch.setattr("getpass.getpass", lambda _prompt: "test-password")

    with caplog.at_level(logging.WARNING, logger="annofabcli.common.cli"):
        service = build_annofabapi_resource(args)

    assert service.api.credentials == expected_credentials
    warnings = [record for record in caplog.records if record.name == "annofabcli.common.cli" and record.levelno == logging.WARNING]
    if isinstance(expected_credentials, IdPass):
        assert len(warnings) == 1
        assert "--annofab_pat" in warnings[0].getMessage()
        assert "ANNOFAB_PAT" in warnings[0].getMessage()
    else:
        assert warnings == []
    assert "test-user" not in caplog.text
    assert "test-password" not in caplog.text
    assert "command-line-token" not in caplog.text
    assert "environment-token" not in caplog.text


def test_get_json_from_args():
    expected = {"foo": 1}
    assert get_json_from_args('{"foo": 1}') == expected
    assert get_json_from_args("file://tests/data/arg.json") == expected
    assert get_json_from_args(None) is None


def test_get_list_from_args():
    expected = ["id1", "id2", "id3"]

    actual = get_list_from_args(["id1", "id2", "id3"])
    assert all(a == b for a, b in zip(actual, expected, strict=False))

    actual = get_list_from_args(["file://tests/data/arg_id_list.txt"])
    assert all(a == b for a, b in zip(actual, expected, strict=False))

    actual = get_list_from_args(None)
    assert len(actual) == 0


def test_get_endpoint_url_prefers_command_line_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANNOFAB_ENDPOINT_URL", "https://environment.example.com")

    args = argparse.Namespace(endpoint_url="https://command-line.example.com")

    assert get_endpoint_url(args) == "https://command-line.example.com"


def test_get_endpoint_url_uses_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANNOFAB_ENDPOINT_URL", "https://environment.example.com")

    args = argparse.Namespace(endpoint_url=None)

    assert get_endpoint_url(args) == "https://environment.example.com"


def test_get_endpoint_url_uses_default_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANNOFAB_ENDPOINT_URL", raising=False)

    args = argparse.Namespace(endpoint_url=None)

    assert get_endpoint_url(args) == DEFAULT_ENDPOINT_URL


@pytest.mark.parametrize("value", ["1", "3"])
def test_positive_int(value: str) -> None:
    assert positive_int(value) == int(value)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_positive_int_rejects_non_positive_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)


def test_non_negative_int() -> None:
    assert non_negative_int("0") == 0
    assert non_negative_int("3") == 3

    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int("-1")


def test_prompt_yesnoall_uses_lowercase_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_list = []

    def input_mock(prompt: str) -> str:
        prompt_list.append(prompt)
        return "all"

    monkeypatch.setattr(builtins, "input", input_mock)

    assert prompt_yesnoall("処理しますか？") == (True, True)
    assert prompt_list == ["処理しますか？ [y/n/all] : "]


def test_prompt_yesnoall_accepts_uppercase_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "input", lambda _prompt: "ALL")

    assert prompt_yesnoall("処理しますか？") == (True, True)


@pytest.mark.parametrize(("answer", "expected"), [("y", True), ("Y", True), ("n", False), ("N", False)])
def test_prompt_yesno_rejects_all(monkeypatch: pytest.MonkeyPatch, answer: str, *, expected: bool) -> None:
    responses = iter(["all", "ALL", answer])
    prompts: list[str] = []

    def input_mock(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(builtins, "input", input_mock)

    assert prompt_yesno("処理を続行しますか？") is expected
    assert prompts == ["処理を続行しますか？ [y/n] : "] * 3
