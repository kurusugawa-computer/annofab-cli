import json
from unittest.mock import Mock

from annofabcli.__main__ import main


def test_shared_input_data_counts_each_task(monkeypatch, tmp_path):
    monkeypatch.setattr("annofabcli.common.video_duration.build_annofabapi_resource_and_login", Mock(side_effect=AssertionError("ローカル処理で認証してはいけません")))
    task_json = tmp_path / "task.json"
    input_data_json = tmp_path / "input_data.json"
    output = tmp_path / "out.html"
    task_json.write_text(
        json.dumps([{"project_id": "p", "task_id": task_id, "phase": "annotation", "phase_stage": 1, "status": "not_started", "input_data_id_list": ["i"]} for task_id in ["t1", "t2"]])
    )
    input_data_json.write_text(json.dumps([{"input_data_id": "i", "input_data_name": "video.mp4", "updated_datetime": "2026-10-06T12:00:00+09:00", "system_metadata": {"input_duration": 10}}]))
    main(["task", "visualize_video_duration", "--task_json", str(task_json), "--input_data_json", str(input_data_json), "--output", str(output)])
    assert json.dumps("タスク数")[1:-1] in output.read_text()
    assert "N=2" in output.read_text()
