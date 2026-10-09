import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import TaskQuery
from annofabcli.task.list_all_tasks import ListTasksWithJsonMain


@pytest.mark.parametrize("use_temp_dir", [False, True])
@pytest.mark.parametrize("is_latest", [False, True])
def test_downloaded_tasks_are_filtered_and_enriched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, use_temp_dir: bool, is_latest: bool) -> None:
    task = json.loads((Path(__file__).parents[1] / "data/task.json").read_text(encoding="utf-8"))[0]
    task["task_id"] = "task1"
    task["metadata"] = {}
    task["operation_updated_datetime"] = task["updated_datetime"]
    for history in task["histories_by_phase"]:
        history["worked"] = True
    other_task = {**task, "task_id": "task2"}

    expected_latest = is_latest

    def download(project_id: str, dest_dir: Path, *, is_latest: bool) -> Path:
        assert project_id == "project1"
        assert is_latest is expected_latest
        path = dest_dir / "tasks.json"
        path.write_text(json.dumps([task, other_task]), encoding="utf-8")
        return path

    downloading = Mock(side_effect=download)
    monkeypatch.setattr(DownloadingFile, "download_task_json_to_dir", downloading)
    service = Mock()
    service.wrapper.get_all_project_members.return_value = []

    result = ListTasksWithJsonMain(service).get_task_list(
        "project1",
        task_id_list=["task1"],
        task_query=TaskQuery.from_dict({"status": "break"}),
        is_latest=is_latest,
        temp_dir=tmp_path if use_temp_dir else None,
    )

    assert [task["task_id"] for task in result] == ["task1"]
    assert result[0]["input_data_count"] == 1
    assert result[0]["worktime_hour"] == pytest.approx(539662 / 3600000)
    assert "number_of_rejections" not in result[0]
    assert downloading.call_args.kwargs["is_latest"] is is_latest
