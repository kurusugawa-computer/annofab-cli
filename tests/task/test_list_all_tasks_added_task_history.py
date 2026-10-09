import json
from pathlib import Path
from unittest.mock import MagicMock

from annofabcli.task.list_all_tasks_added_task_history import ListAllTasksAddedTaskHistoryMain


def test_load_downloaded_task_history(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    histories = {"task1": [{"task_history_id": "history1"}]}
    path.write_text(json.dumps(histories), encoding="utf-8")
    service = MagicMock()
    main_obj = ListAllTasksAddedTaskHistoryMain(service, "project1")
    downloading_obj = MagicMock()
    downloading_obj.download_task_history_json_to_dir.return_value = path
    main_obj.downloading_obj = downloading_obj
    actual = main_obj.load_task_history_dict(tmp_path)
    assert actual == histories
    downloading_obj.download_task_history_json_to_dir.assert_called_once_with("project1", tmp_path)


def test_load_task_list_updates_task_json_when_latest_task_is_specified(tmp_path):
    task_json_path = tmp_path / "task.json"
    task_list = [{"task_id": "task-1"}]
    task_json_path.write_text(json.dumps(task_list), encoding="utf-8")

    main_obj = ListAllTasksAddedTaskHistoryMain(MagicMock(), "project-1")
    downloading_obj = MagicMock()
    downloading_obj.download_task_json_to_dir.return_value = task_json_path
    main_obj.downloading_obj = downloading_obj

    actual = main_obj.load_task_list(temp_dir=tmp_path, is_latest=True)

    assert actual == task_list
    downloading_obj.download_task_json_to_dir.assert_called_once_with("project-1", tmp_path, is_latest=True)
