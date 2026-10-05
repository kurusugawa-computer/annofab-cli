import json

import annofabapi

from annofabcli.__main__ import main


def test_local_input_data_without_task_json(monkeypatch, tmp_path):
    monkeypatch.setattr("annofabcli.common.video_duration.build_annofabapi_resource_and_login", lambda _args: annofabapi.build())
    input_data_json = tmp_path / "input_data.json"
    output = tmp_path / "out.html"
    input_data_json.write_text(json.dumps([{"input_data_id": "i", "input_data_name": "video.mp4", "updated_datetime": "2026-10-06T12:00:00+09:00", "system_metadata": {"input_duration": 10}}]))
    main(["input_data", "visualize_video_duration", "--input_data_json", str(input_data_json), "--output", str(output)])
    assert json.dumps("入力データ数")[1:-1] in output.read_text()
    assert "N=1" in output.read_text()
