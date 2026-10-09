import json

import pandas
import pytest

from annofabcli.common.enums import OutputFormat
from annofabcli.task_count.output import print_task_count_summary


@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.PRETTY_JSON])
def test_summary_json_preserves_keys_numbers_and_missing_values(output_format, tmp_path):
    df = pandas.DataFrame(
        {
            "phase": ["annotation", "inspection"],
            "metadata.dataset": ["train", float("nan")],
            "task_count": pandas.Series([2, 0], dtype="Int64"),
            "video_duration_hour": [0.5, 1.25],
            "username": pandas.Series(["日本語", pandas.NA], dtype="string"),
        }
    )
    output = tmp_path / "summary.json"

    print_task_count_summary(df, format=output_format, output=output)

    contents = output.read_text(encoding="utf-8")
    assert "NaN" not in contents
    assert json.loads(contents) == [
        {"phase": "annotation", "metadata.dataset": "train", "task_count": 2, "video_duration_hour": 0.5, "username": "日本語"},
        {"phase": "inspection", "metadata.dataset": None, "task_count": 0, "video_duration_hour": 1.25, "username": None},
    ]
    assert isinstance(json.loads(contents)[0]["task_count"], int)
    if output_format == OutputFormat.PRETTY_JSON:
        assert "\n" in contents


@pytest.mark.parametrize("output_format", [OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON])
def test_empty_summary_output(output_format, tmp_path):
    df = pandas.DataFrame(columns=["phase", "complete"])
    output = tmp_path / "summary"

    print_task_count_summary(df, format=output_format, output=output)

    if output_format == OutputFormat.CSV:
        actual = pandas.read_csv(output)
        assert actual.columns.to_list() == ["phase", "complete"]
        assert len(actual) == 0
    else:
        assert json.loads(output.read_text()) == []


def test_summary_csv_preserves_existing_output(tmp_path):
    df = pandas.DataFrame({"phase": ["annotation"], "complete": [2.0]})
    output = tmp_path / "summary.csv"

    print_task_count_summary(df, format=OutputFormat.CSV, output=output)

    assert output.read_text(encoding="utf-8-sig") == "phase,complete\nannotation,2.0\n"


def test_summary_json_to_stdout(capsys):
    print_task_count_summary(pandas.DataFrame([{"task_id_group": "train", "acceptance.complete": 3}]), format=OutputFormat.JSON)

    assert json.loads(capsys.readouterr().out) == [{"task_id_group": "train", "acceptance.complete": 3}]
