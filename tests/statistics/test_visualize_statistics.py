import logging
from pathlib import Path

import pytest

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.statistics.visualize_statistics import read_actual_worktime


@pytest.mark.parametrize("option_name", ["actual_worktime_csv", "labor_csv"])
def test_read_actual_worktime(option_name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    csv_path = tmp_path / "actual_worktime.csv"
    csv_path.write_text("project_id,date,account_id,actual_worktime_hour\n001,2026-10-05,002,1.5\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        actual = read_actual_worktime(
            actual_worktime_csv=csv_path if option_name == "actual_worktime_csv" else None,
            labor_csv=csv_path if option_name == "labor_csv" else None,
        )

    assert actual.df.to_dict("records") == [{"project_id": "001", "date": "2026-10-05", "account_id": "002", "actual_worktime_hour": 1.5}]
    if option_name == "labor_csv":
        assert "非推奨" in caplog.text
        assert "--actual_worktime_csv" in caplog.text
        assert "2027/01/01以降に廃止予定" in caplog.text
    else:
        assert not caplog.records


def test_read_actual_worktime_without_csv(caplog: pytest.LogCaptureFixture) -> None:
    actual = read_actual_worktime(actual_worktime_csv=None, labor_csv=None)

    assert actual.is_empty()
    assert "--actual_worktime_csv" in caplog.text


@pytest.mark.parametrize("option_name", ["actual_worktime_csv", "labor_csv"])
def test_read_actual_worktime_missing_columns(option_name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    csv_path = tmp_path / "actual_worktime.csv"
    csv_path.write_text("project_id,date,account_id\n001,2026-10-05,002\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        read_actual_worktime(
            actual_worktime_csv=csv_path if option_name == "actual_worktime_csv" else None,
            labor_csv=csv_path if option_name == "labor_csv" else None,
        )

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    error_messages = [record.message for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_messages) == 1
    assert f"--{option_name}" in error_messages[0]
    assert "actual_worktime_hour" in error_messages[0]
