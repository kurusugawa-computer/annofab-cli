import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.annotation_specs.history import (
    JST,
    find_histories_by_updated_datetime,
    get_history_id_from_before_index,
    load_annotation_specs_or_exit,
    parse_updated_datetime,
    resolve_history_id_or_exit,
)


@pytest.mark.parametrize(
    ("value", "expected_start", "expected_delta"),
    [
        ("2025-03-07", datetime.datetime(2025, 3, 7, tzinfo=JST), datetime.timedelta(days=1)),
        ("2025-03-07T14:30", datetime.datetime(2025, 3, 7, 14, 30, tzinfo=JST), datetime.timedelta(minutes=1)),
        ("2025-03-07T14:30:15", datetime.datetime(2025, 3, 7, 14, 30, 15, tzinfo=JST), datetime.timedelta(seconds=1)),
        ("2025-03-07T05:30:15Z", datetime.datetime(2025, 3, 7, 5, 30, 15, tzinfo=datetime.UTC), datetime.timedelta(seconds=1)),
        ("2025-03-07T14:30:15.12+09:00", datetime.datetime(2025, 3, 7, 14, 30, 15, 120000, tzinfo=JST), datetime.timedelta(milliseconds=10)),
    ],
)
def test_parse_updated_datetime(value: str, expected_start: datetime.datetime, expected_delta: datetime.timedelta) -> None:
    actual = parse_updated_datetime(value)

    assert actual.start == expected_start
    assert actual.end - actual.start == expected_delta


@pytest.mark.parametrize("value", ["2025/03/07", "2025-03-07 14:30", "2025-02-30", "2025-03-07T25:00", "2025-03-07T14"])
def test_parse_updated_datetime_不正な値(value: str) -> None:
    with pytest.raises(ValueError):
        parse_updated_datetime(value)


def test_find_histories_by_updated_datetime_日付かつJSTで検索する() -> None:
    histories = [
        {"history_id": "previous_day", "updated_datetime": "2025-03-06T14:59:59Z"},
        {"history_id": "first", "updated_datetime": "2025-03-06T15:00:00Z"},
        {"history_id": "last", "updated_datetime": "2025-03-07T14:59:59.999999Z"},
        {"history_id": "next_day", "updated_datetime": "2025-03-07T15:00:00Z"},
    ]

    actual = find_histories_by_updated_datetime(histories, "2025-03-07")

    assert [history["history_id"] for history in actual] == ["last", "first"]


def test_find_histories_by_updated_datetime_指定したタイムゾーンで検索する() -> None:
    histories = [
        {"history_id": "matched", "updated_datetime": "2025-03-07T14:30:15+09:00"},
        {"history_id": "not_matched", "updated_datetime": "2025-03-07T14:30:16+09:00"},
    ]

    actual = find_histories_by_updated_datetime(histories, "2025-03-07T05:30:15Z")

    assert [history["history_id"] for history in actual] == ["matched"]


def test_get_history_id_from_before_index_更新日時の新しい順に選択する() -> None:
    service = Mock()
    service.api.get_annotation_specs_histories.return_value = (
        [
            {"history_id": "middle", "updated_datetime": "2025-03-02T00:00:00Z"},
            {"history_id": "latest", "updated_datetime": "2025-03-03T00:00:00Z"},
            {"history_id": "oldest", "updated_datetime": "2025-03-01T00:00:00Z"},
        ],
        None,
    )

    assert get_history_id_from_before_index(service, "project_id", 1) == "middle"


def test_resolve_history_id_or_exit_複数件なら候補を表示して終了する(capsys: pytest.CaptureFixture[str]) -> None:
    service = Mock()
    service.api.get_annotation_specs_histories.return_value = (
        [
            {"history_id": "history1", "updated_datetime": "2025-03-07T10:00:00+09:00", "comment": "first"},
            {"history_id": "history2", "updated_datetime": "2025-03-07T11:00:00+09:00", "comment": "second"},
        ],
        None,
    )

    with pytest.raises(SystemExit):
        resolve_history_id_or_exit(
            service,
            "project_id",
            history_id=None,
            before=None,
            updated_datetime="2025-03-07",
            common_message="command: error:",
        )

    assert "history2" in capsys.readouterr().err


def test_resolve_history_id_or_exit_1件ならhistory_idを返す() -> None:
    service = Mock()
    service.api.get_annotation_specs_histories.return_value = (
        [{"history_id": "history1", "updated_datetime": "2025-03-07T10:00:00+09:00", "comment": None}],
        None,
    )

    actual = resolve_history_id_or_exit(
        service,
        "project_id",
        history_id=None,
        before=None,
        updated_datetime="2025-03-07",
        common_message="command: error:",
    )

    assert actual == "history1"


def test_resolve_history_id_or_exit_0件なら終了する() -> None:
    service = Mock()
    service.api.get_annotation_specs_histories.return_value = ([], None)

    with pytest.raises(SystemExit):
        resolve_history_id_or_exit(
            service,
            "project_id",
            history_id=None,
            before=None,
            updated_datetime="2025-03-07",
            common_message="command: error:",
        )


def test_load_annotation_specs_or_exit_JSONファイルと履歴指定は併用できない(tmp_path: Path) -> None:
    json_file = tmp_path / "annotation_specs.json"
    json_file.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit):
        load_annotation_specs_or_exit(
            Mock(),
            project_id=None,
            annotation_specs_json_file=json_file,
            history_id=None,
            before=None,
            updated_datetime="2025-03-07",
            common_message="command: error:",
        )
