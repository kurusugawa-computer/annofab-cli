import argparse
import builtins

import pytest

from annofabcli.common.cli import get_json_from_args, get_list_from_args, non_negative_int, prompt_yesnoall


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
