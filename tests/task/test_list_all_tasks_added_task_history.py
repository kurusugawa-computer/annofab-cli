import json
from unittest.mock import MagicMock

from annofabcli.task.list_all_tasks_added_task_history import ListAllTasksAddedTaskHistoryMain


def test_load_task_list_updates_task_json_when_latest_task_is_specified(tmp_path):
    task_json_path = tmp_path / "task.json"
    task_list = [{"task_id": "task-1"}]
    task_json_path.write_text(json.dumps(task_list), encoding="utf-8")

    main_obj = ListAllTasksAddedTaskHistoryMain(MagicMock(), "project-1")
    downloading_obj = MagicMock()
    downloading_obj.download_task_json_to_dir.return_value = task_json_path
    main_obj.downloading_obj = downloading_obj

    actual = main_obj.load_task_list(task_json_path=None, temp_dir=tmp_path, is_latest=True)

    assert actual == task_list
    downloading_obj.download_task_json_to_dir.assert_called_once_with("project-1", tmp_path, is_latest=True)
