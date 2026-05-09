from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.task import put_tasks
from annofabcli.task.task_creation import (
    get_task_relation_dict_from_header_csv,
    get_task_relation_dict_from_headerless_csv,
    get_task_relation_dict_from_json_args,
)


def test_get_task_relation_dict_from_header_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text(
        "input_data_id,task_id,extra\ninput_data_001,task_001,a\ninput_data_002,task_001,b\ninput_data_003,task_002,c\n",
        encoding="utf-8",
    )

    actual = get_task_relation_dict_from_header_csv(csv_file)

    assert actual == {
        "task_001": ["input_data_001", "input_data_002"],
        "task_002": ["input_data_003"],
    }


def test_get_task_relation_dict_from_header_csv_with_missing_column(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_id\nfoo\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        get_task_relation_dict_from_header_csv(csv_file)

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE


def test_get_task_relation_dict_from_headerless_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "task.csv"
    csv_file.write_text("task_001,input_data_001\ntask_001,input_data_002\n", encoding="utf-8")

    actual = get_task_relation_dict_from_headerless_csv(csv_file)

    assert actual == {
        "task_001": ["input_data_001", "input_data_002"],
    }


def test_get_task_relation_dict_from_json_args_with_invalid_json() -> None:
    with pytest.raises(SystemExit) as exc_info:
        get_task_relation_dict_from_json_args('["task_001"]', command_name="annofabcli task create")

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE


def test_task_put_main_prints_deprecated_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    dummy_service = Mock()
    dummy_facade = Mock()

    monkeypatch.setattr(put_tasks, "build_annofabapi_resource_and_login", lambda _args: dummy_service)
    monkeypatch.setattr(put_tasks, "AnnofabApiFacade", lambda _service: dummy_facade)

    called = {"main": False}

    class StubPutTask:
        def __init__(self, service, facade, args):
            assert service is dummy_service
            assert facade is dummy_facade
            called["args"] = args

        def main(self):
            called["main"] = True

    monkeypatch.setattr(put_tasks, "PutTask", StubPutTask)

    args = Namespace()
    put_tasks.main(args)

    captured = capsys.readouterr()
    assert "[DEPRECATED]" in captured.err
    assert "`task create`" in captured.err
    assert called["main"] is True
