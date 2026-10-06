import csv
import json

import pytest
from annofabapi.models import InputData, Task

from annofabcli.common.enums import OutputFormat
from annofabcli.common.video_duration import get_task_video_duration_list, get_video_durations, print_task_video_duration_list
from annofabcli.common.video_duration_histogram import TimeUnit, plot_video_duration
from annofabcli.statistics.list_video_duration import get_video_duration_list as get_legacy_rows


@pytest.fixture
def task_list() -> list[Task]:
    return json.loads("""[
        {"project_id":"p", "task_id":"t1", "phase":"annotation", "phase_stage":1, "status":"not_started", "input_data_id_list":["shared"]},
        {"project_id":"p", "task_id":"t2", "phase":"annotation", "phase_stage":1, "status":"not_started", "input_data_id_list":["shared"]},
        {"project_id":"p", "task_id":"t3", "phase":"annotation", "phase_stage":1, "status":"not_started", "input_data_id_list":["unknown"]},
        {"project_id":"p", "task_id":"t4", "phase":"annotation", "phase_stage":1, "status":"not_started", "input_data_id_list":["missing"]}
    ]""")


@pytest.fixture
def input_data_list() -> list[InputData]:
    return json.loads("""[
        {"input_data_id":"shared", "input_data_name":"shared.mp4", "updated_datetime":"2026-10-06T23:59:00+09:00", "system_metadata":{"input_duration":10}},
        {"input_data_id":"unused", "input_data_name":"unused.mp4", "updated_datetime":"2026-10-07T00:00:00+09:00", "system_metadata":{"input_duration":20}},
        {"input_data_id":"unknown", "input_data_name":"unknown.mp4", "updated_datetime":"2026-10-06T00:00:00+09:00", "system_metadata":{"input_duration":null}},
        {"input_data_id":"zero", "input_data_name":"zero.mp4", "updated_datetime":"2026-10-06T12:00:00+09:00", "system_metadata":{"input_duration":0}}
    ]""")


def test_shared_and_unused_input_data(task_list, input_data_list):
    assert get_video_durations(task_list, input_data_list) == ([10, 10], 2)


def test_filtering_and_date_boundaries(task_list, input_data_list):
    assert get_video_durations(task_list, input_data_list, task_ids=["t2"]) == ([10], 0)
    assert get_video_durations(task_list, input_data_list, input_data_ids=["shared"]) == ([10, 10], 0)
    assert get_video_durations(task_list, input_data_list, from_date="2026-10-06", to_date="2026-10-06") == ([10, 10], 1)
    assert get_video_durations(task_list, input_data_list, from_date="2026-10-07") == ([], 0)


def test_rows_and_missing_values(task_list, input_data_list, tmp_path):
    rows = get_task_video_duration_list(task_list, input_data_list)
    assert rows[0] == {
        "project_id": "p",
        "task_id": "t1",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
        "input_data_id": "shared",
        "input_data_name": "shared.mp4",
        "video_duration_second": 10,
        "input_data_updated_datetime": "2026-10-06T23:59:00+09:00",
    }
    assert rows[2]["video_duration_second"] is None
    assert rows[3]["input_data_name"] is None
    assert rows[3]["input_data_updated_datetime"] is None
    json_file = tmp_path / "rows.json"
    csv_file = tmp_path / "rows.csv"
    print_task_video_duration_list(rows, OutputFormat.JSON, json_file)
    print_task_video_duration_list(rows, OutputFormat.CSV, csv_file)
    assert json.loads(json_file.read_text()) == rows
    with csv_file.open(encoding="utf-8-sig", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    assert set(csv_rows[0]) == set(rows[0])
    assert csv_rows[2]["video_duration_second"] == ""
    assert csv_rows[3]["input_data_updated_datetime"] == ""


def test_empty_outputs(tmp_path):
    json_file = tmp_path / "empty.json"
    csv_file = tmp_path / "empty.csv"
    print_task_video_duration_list([], OutputFormat.PRETTY_JSON, json_file)
    print_task_video_duration_list([], OutputFormat.CSV, csv_file)
    assert json.loads(json_file.read_text()) == []
    assert csv_file.read_text(encoding="utf-8-sig").splitlines() == ["project_id,task_id,phase,phase_stage,status,input_data_id,input_data_name,video_duration_second,input_data_updated_datetime"]


@pytest.mark.parametrize("input_data_ids", [[], ["shared", "shared"]])
def test_invalid_task_input_data_count(task_list, input_data_list, input_data_ids):
    task_list[0]["input_data_id_list"] = input_data_ids
    with pytest.raises(ValueError):
        get_task_video_duration_list(task_list, input_data_list)


def test_legacy_schema_is_preserved(task_list, input_data_list):
    rows = get_legacy_rows(task_list, input_data_list)
    assert rows[0]["task_phase"] == "annotation"
    assert rows[0]["task_status"] == "not_started"
    assert rows[2]["video_duration_second"] == 0
    assert "input_data_updated_datetime" not in rows[3]


@pytest.mark.parametrize("durations", [[], [0], [10, 10]])
@pytest.mark.parametrize("bin_width", [None, 60])
def test_histogram_outputs(durations, bin_width, tmp_path):
    output = tmp_path / "out.html"
    plot_video_duration(durations, output, time_unit=TimeUnit.MINUTE, bin_width=bin_width, y_axis_label="タスク数", excluded_count=2)
    html = output.read_text()
    assert json.dumps("タスク数")[1:-1] in html
    assert json.dumps("除外した件数: 2件")[1:-1] in html
    if not durations:
        assert json.dumps("対象0件")[1:-1] in html


@pytest.mark.parametrize("bin_width", [0, -1, float("inf"), float("nan")])
def test_invalid_bin_width(bin_width, tmp_path):
    with pytest.raises(ValueError):
        plot_video_duration([10], tmp_path / "out.html", time_unit=TimeUnit.SECOND, bin_width=bin_width)


def test_zero_duration_is_included(task_list, input_data_list):
    task_list[0]["input_data_id_list"] = ["zero"]
    assert get_video_durations(task_list[:1], input_data_list) == ([0], 0)
