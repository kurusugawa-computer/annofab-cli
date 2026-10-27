import copy
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import annofabapi
import pandas
import pytest
from annofabapi.credentials import IdPass

from annofabcli.common.enums import OutputFormat
from annofabcli.task import list_all_with_statistics as command
from tests.task.test_list_tasks_added_task_history import complete_task, task_created_immediately


@pytest.fixture
def command_context(tmp_path, monkeypatch):
    tasks = []
    histories = {}
    for task_id, info in [("pending", task_created_immediately), ("completed", complete_task), ("missing", task_created_immediately), ("empty", task_created_immediately)]:
        task = copy.deepcopy(info.task)
        task.update(project_id="p", task_id=task_id, input_data_id_list=[task_id], metadata={"category": "sample", "priority": 1})
        tasks.append(task)
        histories[task_id] = copy.deepcopy(info.task_histories)

    inputs = [
        {"input_data_id": task_id, "input_data_name": task_id, "updated_datetime": "2026-10-01T00:00:00+09:00", "system_metadata": {"input_duration": seconds}}
        for task_id, seconds in [("pending", 120), ("completed", None), ("missing", 0), ("empty", 60)]
    ]
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for task_id, details in [
            (
                "pending",
                [
                    {"label": "car", "data": {"_type": "Range", "begin": 0, "end": 60000}},
                    {"label": "car", "data": {"_type": "Range", "begin": 30000, "end": 90000}},
                    {"label": "scene", "data": {"_type": "Classification"}},
                ],
            ),
            ("completed", [{"label": "scene", "data": {"_type": "Classification"}}]),
            ("empty", []),
        ]:
            archive.writestr(f"{task_id}/{task_id}.json", json.dumps({"task_id": task_id, "input_data_id": task_id, "details": details}))

    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(command, "build_annofabapi_resource_and_login", Mock(return_value=service))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": "owner"}, None)))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test", "input_data_type": "movie"}, None)))
    monkeypatch.setattr(service.api, "get_annotation_specs", Mock(return_value=({"labels": []}, None)))
    account_ids = {history["account_id"] for task_histories in histories.values() for history in task_histories if history["account_id"] is not None} | {"a"}
    members = [{"account_id": account_id, "user_id": account_id, "username": account_id} for account_id in sorted(account_ids)]
    monkeypatch.setattr(service.wrapper, "get_all_project_members", Mock(return_value=members))
    monkeypatch.setattr(service.wrapper, "download_project_tasks_url", Mock(side_effect=lambda _p, dest: Path(dest).write_text(json.dumps(tasks), encoding="utf-8")))
    monkeypatch.setattr(service.wrapper, "download_project_task_histories_url", Mock(side_effect=lambda _p, dest: Path(dest).write_text(json.dumps(histories), encoding="utf-8")))
    monkeypatch.setattr(service.wrapper, "download_project_inputs_url", Mock(side_effect=lambda _p, dest: Path(dest).write_text(json.dumps(inputs), encoding="utf-8")))
    monkeypatch.setattr(service.wrapper, "download_annotation_archive", Mock(side_effect=lambda _p, dest: shutil.copyfile(archive_path, dest)))
    monkeypatch.setattr(service.api, "get_task_histories", Mock(side_effect=lambda _p, task_id: (copy.deepcopy(histories[task_id]), None)))
    monkeypatch.setattr(service.api, "get_annotation_list", Mock(return_value=({"total_count": 7}, None)))
    return service, tasks, histories


def run_command(tmp_path: Path, *options: str) -> list[dict[str, Any]]:
    output = tmp_path / "tasks.json"
    args = command.create_parser().parse_args(["--project_id", "p", "--output", str(output), "--format", "pretty_json", *options])
    args.subcommand_func(args)
    return json.loads(output.read_text(encoding="utf-8"))


def test_all_states_and_zero_missing_and_non_range_annotations(command_context, tmp_path):
    service, _, _ = command_context
    rows = run_command(tmp_path)
    assert [row["task_id"] for row in rows] == ["pending", "completed", "missing", "empty"]
    assert [row["annotation_count"] for row in rows] == [3, 1, None, 0]
    assert [row["annotation_duration_minute"] for row in rows] == [2, 0, None, 0]
    assert [row["video_duration_minute"] for row in rows] == [2, None, 0, 1]
    assert rows[0]["status"] == "not_started"
    assert rows[1]["phase"] == "acceptance"
    assert rows[0]["metadata"] == {"category": "sample", "priority": 1}
    assert set(rows[0]) == set(command.get_output_columns()) | {"metadata"}
    service.api.get_task_histories.assert_not_called()
    service.api.get_annotation_list.assert_not_called()


@pytest.mark.parametrize(("option", "label"), [("--production_volume_include_label", "car"), ("--production_volume_exclude_label", "scene")])
@pytest.mark.usefixtures("command_context")
def test_label_filter_only_changes_annotation_volume(tmp_path, option, label):
    original = run_command(tmp_path)
    path = tmp_path / "labels.txt"
    path.write_text(label + "\n", encoding="utf-8")
    filtered = run_command(tmp_path, option, f"file://{path}")
    assert [row["annotation_count"] for row in filtered] == [2, 0, None, 0]
    assert [row["annotation_duration_minute"] for row in filtered] == [2, 0, None, 0]
    for before, after in zip(original, filtered, strict=True):
        assert before["worktime_hour"] == after["worktime_hour"]
        assert before["video_duration_minute"] == after["video_duration_minute"]
        assert before["input_data_count"] == after["input_data_count"]


def test_history_api_only_fetches_filtered_tasks_and_refreshes_total_worktime(command_context, tmp_path):
    service, _, histories = command_context
    histories["pending"][0]["started_datetime"] = "2026-10-01T00:00:00+09:00"
    history = copy.deepcopy(histories["pending"][0])
    history.update(started_datetime="2026-10-01T00:00:00+09:00", accumulated_labor_time_milliseconds="PT1H", account_id="a")
    histories["pending"].append(history)
    rows = run_command(tmp_path, "--get_task_histories_one_of_each", "--task_id", "pending", "--task_query", '{"status":"not_started"}')
    assert len(rows) == 1
    assert rows[0]["annotation_worktime_hour"] == 1
    assert rows[0]["worktime_hour"] == 1
    assert rows[0]["first_annotation_started_datetime"] == "2026-10-01T00:00:00+09:00"
    service.wrapper.download_project_task_histories_url.assert_not_called()
    service.api.get_task_histories.assert_called_once_with("p", "pending")


def test_history_api_failure_does_not_output_partial_results(command_context, tmp_path):
    service, _, _ = command_context
    service.api.get_task_histories.side_effect = OSError()
    with pytest.raises(OSError):
        run_command(tmp_path, "--get_task_histories_one_of_each")
    assert not (tmp_path / "tasks.json").exists()


@pytest.mark.parametrize("source", ["zip", "api", "auto"])
def test_count_sources_and_movie_duration(command_context, tmp_path, source):
    service, _, _ = command_context
    if source == "auto":
        service.api.get_annotation_specs.return_value = ({"labels": [{"annotation_type": "user_instance_segment"}]}, None)
    rows = run_command(tmp_path, "--annotation_count_source", source, "--task_id", "pending")
    assert rows[0]["annotation_count"] == (3 if source == "zip" else 7)
    assert rows[0]["annotation_duration_minute"] == 2
    service.wrapper.download_annotation_archive.assert_called_once()
    if source == "zip":
        service.api.get_annotation_list.assert_not_called()
    else:
        assert service.api.get_annotation_list.call_args.kwargs["query_params"]["query"]["task_id"] == "pending"


@pytest.mark.parametrize("input_type", ["image", "3dpc"])
def test_api_counts_without_zip_or_input_download_for_non_movie(command_context, tmp_path, input_type):
    service, _, _ = command_context
    service.api.get_project.return_value = ({"title": "test", "input_data_type": input_type}, None)
    rows = run_command(tmp_path, "--annotation_count_source", "api")
    assert all(row["annotation_count"] == 7 and row["video_duration_minute"] is None and row["annotation_duration_minute"] is None for row in rows)
    service.wrapper.download_annotation_archive.assert_not_called()
    service.wrapper.download_project_inputs_url.assert_not_called()


def test_latest_updates_used_files_but_not_history_archive(command_context, tmp_path, monkeypatch):
    service, _, _ = command_context
    for name in ["post_project_tasks_update", "post_project_inputs_update", "post_annotation_archive_update"]:
        monkeypatch.setattr(service.api, name, Mock(return_value=({"job": {"job_id": "j"}}, None)))
    monkeypatch.setattr(service.wrapper, "wait_for_completion", Mock(return_value=True))
    run_command(tmp_path, "--latest", "--annotation_count_source", "zip")
    service.api.post_annotation_archive_update.assert_called_once()
    service.api.post_project_inputs_update.assert_called_once()
    service.wrapper.download_project_task_histories_url.assert_called_once()


def test_empty_selection_skips_statistics_and_history_download(command_context, tmp_path):
    service, _, _ = command_context
    assert run_command(tmp_path, "--task_id", "unknown") == []
    service.wrapper.download_project_task_histories_url.assert_not_called()
    service.wrapper.download_annotation_archive.assert_not_called()
    service.api.get_annotation_list.assert_not_called()


@pytest.mark.usefixtures("command_context")
def test_csv_fixed_columns_metadata_and_nullable_counts(tmp_path):
    rows = run_command(tmp_path)
    path = tmp_path / "tasks.csv"
    command.output_tasks(rows, path, OutputFormat.CSV)
    df = pandas.read_csv(path)
    assert list(df.columns) == [*command.get_output_columns(), "metadata.category", "metadata.priority"]
    assert len(command.get_output_columns()) == 47
    assert len(df) == 4
    for index, row in enumerate(rows):
        for phase in ["annotation", "inspection", "acceptance"]:
            column = f"{phase}_worktime_hour_by_user"
            assert json.loads(df.loc[index, column]) == row[column]
    assert pandas.isna(df.loc[2, "annotation_count"])
    assert df.loc[3, "annotation_count"] == 0
    assert not any(column.startswith("since_") for column in df.columns)
    assert path.read_text(encoding="utf-8-sig").splitlines()[1].split(",")[13] == "3"


def test_empty_csv_has_all_fixed_headers(tmp_path):
    path = tmp_path / "empty.csv"
    command.output_tasks([], path, OutputFormat.CSV)
    df = pandas.read_csv(path)
    assert list(df.columns) == command.get_output_columns()
    assert df.empty


def test_non_movie_zip_has_blank_duration_columns(command_context, tmp_path):
    service, _, _ = command_context
    service.api.get_project.return_value = ({"title": "test", "input_data_type": "image"}, None)
    rows = run_command(tmp_path, "--annotation_count_source", "zip")
    assert [row["annotation_count"] for row in rows] == [3, 1, None, 0]
    assert all(row["video_duration_minute"] is None and row["annotation_duration_minute"] is None for row in rows)
    service.wrapper.download_project_inputs_url.assert_not_called()


def test_api_count_failure_does_not_output_partial_results(command_context, tmp_path):
    service, _, _ = command_context
    service.api.get_annotation_list.side_effect = [({"total_count": 7}, None), OSError()]
    with pytest.raises(OSError):
        run_command(tmp_path, "--annotation_count_source", "api")
    assert not (tmp_path / "tasks.json").exists()


def test_temp_dir_preserves_downloaded_files(command_context, tmp_path):
    service, _, _ = command_context
    download_dir = tmp_path / "downloads"
    run_command(tmp_path, "--temp_dir", str(download_dir))
    assert sorted(path.suffix for path in download_dir.iterdir()) == [".json", ".json", ".json", ".zip"]
    service.api.get_annotation_list.assert_not_called()
