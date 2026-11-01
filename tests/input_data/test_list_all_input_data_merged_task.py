import json
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pandas
import pytest
from annofabapi.models import JobStatus

from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import UpdatedFileForDownloadingError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_csv
from annofabcli.input_data.list_all_input_data_merged_task import ListInputDataMergedTask, create_df_input_data_with_merged_task, create_parser


def test_empty_list_outputs_input_data_and_task_headers(tmp_path: Path) -> None:
    output = tmp_path / "input_data.csv"
    print_csv(create_df_input_data_with_merged_task([]), output)

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert {"input_data_id", "input_data_name", "input_data_path", "project_id", "task_id", "task_phase", "task_phase_stage", "task_status", "frame_no"} <= set(df.columns)


@pytest.mark.parametrize(
    ("options", "expected_ids"),
    [
        ([], ["input1", "input2", "input3"]),
        (["--input_data_name", "sAmPlE"], ["input1", "input2"]),
        (["--input_data_name", "sample", "OTHER"], ["input1", "input2", "input3"]),
        (["--input_data_name", "missing"], []),
        (["--input_data_name", "file://{names_file}"], ["input1", "input2"]),
        (["--input_data_name", "file://{names_file}", "--input_data_id", "input2", "input3"], ["input2"]),
        (["--input_data_name", "sample", "--input_data_id", "input2", "input3"], ["input2"]),
        (["--input_data_name", "sample", "--input_data_query", '{"input_data_path": "selected"}'], ["input1"]),
    ],
)
def test_main_filters_input_data_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: list[str], expected_ids: list[str]) -> None:
    input_data_list: list[dict[str, object]] = [
        {
            "input_data_id": input_data_id,
            "input_data_name": name,
            "input_data_path": path,
            "project_id": "project1",
            "organization_id": "org1",
            "input_data_set_id": "set1",
            "url": None,
            "etag": None,
            "original_input_data_path": None,
            "updated_datetime": "2026-01-01T00:00:00Z",
            "sign_required": False,
            "metadata": {},
            "system_metadata": {},
        }
        for input_data_id, name, path in [("input1", "Sample-A.jpg", "selected/a.jpg"), ("input2", "sample-B.jpg", "other/b.jpg"), ("input3", "Other.jpg", "selected/c.jpg")]
    ]
    input_data_path = tmp_path / "input_data.json"
    input_data_path.write_text(json.dumps(input_data_list), encoding="utf-8")
    task_path = tmp_path / "tasks.json"
    task_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(DownloadingFile, "download_input_data_json_to_dir", Mock(return_value=input_data_path))
    monkeypatch.setattr(DownloadingFile, "download_task_json_to_dir", Mock(return_value=task_path))
    names_file = tmp_path / "名前一覧.txt"
    names_file.write_text("sAmPlE\n\nmissing\n", encoding="utf-8")
    options = [option.replace("{names_file}", str(names_file)) for option in options]
    output = tmp_path / "result.json"
    args = create_parser().parse_args(["--project_id", "project1", "--format", "json", "--output", str(output), *options])

    ListInputDataMergedTask(Mock(spec=annofabapi.Resource), Mock(spec=AnnofabApiFacade), args).main()

    actual = json.loads(output.read_text(encoding="utf-8"))
    assert [row["input_data_id"] for row in actual] == expected_ids


@pytest.mark.parametrize("latest", [False, True])
@pytest.mark.parametrize("use_temp_dir", [False, True])
def test_download_json_files_requests_both_updates_before_waiting(tmp_path, latest, use_temp_dir):
    service = Mock()
    for method in [service.api.post_project_inputs_update, service.api.post_project_tasks_update]:
        method.return_value = ({"job": {"job_id": "job"}}, None)

    def wait_for_job(*_args, **_kwargs):
        service.api.post_project_inputs_update.assert_called_once_with("p")
        service.api.post_project_tasks_update.assert_called_once_with("p")
        service.wrapper.download_project_inputs_json.assert_not_called()
        service.wrapper.download_project_tasks_json.assert_not_called()
        return JobStatus.SUCCEEDED

    service.wrapper.wait_until_job_finished.side_effect = wait_for_job
    inputs = [{"input_data_id": "input"}]
    tasks = [{"task_id": "task", "input_data_id_list": ["input"]}]
    service.wrapper.download_project_inputs_json.side_effect = lambda _p, dest: Path(dest).write_text(json.dumps(inputs), encoding="utf-8")
    service.wrapper.download_project_tasks_json.side_effect = lambda _p, dest: Path(dest).write_text(json.dumps(tasks), encoding="utf-8")
    args = create_parser().parse_args(["--project_id", "p"])
    command = ListInputDataMergedTask(service, Mock(spec=AnnofabApiFacade), args)
    assert command.download_json_files("p", tmp_path if use_temp_dir else None, is_latest=latest) == (inputs, tasks)
    assert service.wrapper.wait_until_job_finished.call_count == (2 if latest else 0)
    if not latest:
        service.api.post_project_inputs_update.assert_not_called()
        service.api.post_project_tasks_update.assert_not_called()
    service.api.post_annotation_archive_update.assert_not_called()


def test_failed_latest_update_waits_for_other_job_without_downloading(tmp_path):
    service = Mock()
    for method in [service.api.post_project_inputs_update, service.api.post_project_tasks_update]:
        method.return_value = ({"job": {"job_id": "job"}}, None)
    service.wrapper.wait_until_job_finished.side_effect = [JobStatus.FAILED, JobStatus.SUCCEEDED]
    args = create_parser().parse_args(["--project_id", "p"])
    command = ListInputDataMergedTask(service, Mock(spec=AnnofabApiFacade), args)
    with pytest.raises(UpdatedFileForDownloadingError):
        command.download_json_files("p", tmp_path, is_latest=True)
    assert service.wrapper.wait_until_job_finished.call_count == 2
    service.wrapper.download_project_inputs_json.assert_not_called()
    service.wrapper.download_project_tasks_json.assert_not_called()
    assert list(tmp_path.iterdir()) == []
