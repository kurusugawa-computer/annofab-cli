import json
from unittest.mock import Mock

from annofabcli.__main__ import main


def test_local_list_video_duration(monkeypatch, tmp_path):
    monkeypatch.setattr("annofabcli.common.video_duration.build_annofabapi_resource_and_login", Mock(side_effect=AssertionError("ローカル処理で認証してはいけません")))
    task_json = tmp_path / "task.json"
    input_data_json = tmp_path / "input_data.json"
    output = tmp_path / "out.json"
    task_json.write_text(json.dumps([{"project_id": "p", "task_id": "t", "phase": "annotation", "phase_stage": 1, "status": "not_started", "input_data_id_list": ["i"]}]))
    input_data_json.write_text(json.dumps([{"input_data_id": "i", "input_data_name": "video.mp4", "updated_datetime": "2026-10-06T12:00:00+09:00", "system_metadata": {"input_duration": 10}}]))
    main(["task", "list_video_duration", "--task_json", str(task_json), "--input_data_json", str(input_data_json), "--format", "pretty_json", "--output", str(output)])
    rows = json.loads(output.read_text())
    assert rows[0]["video_duration_second"] == 10
    assert rows[0]["phase"] == "annotation"
    assert "task_phase" not in rows[0]
