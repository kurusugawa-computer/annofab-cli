import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from annofabapi.models import JobStatus

from annofabcli.statistics.visualization.visualization_source_files import VisualizationSourceFiles


class TestVisualizationSourceFiles:
    @pytest.fixture
    def mock_service(self):
        return Mock()

    @pytest.fixture
    def visualization_source_files(self, mock_service, tmp_path):
        return VisualizationSourceFiles(annofab_service=mock_service, project_id="test_project", target_dir=tmp_path)

    def test_init(self, visualization_source_files, tmp_path):
        """初期化のテスト"""
        assert visualization_source_files.project_id == "test_project"
        assert visualization_source_files.target_dir == tmp_path
        assert visualization_source_files.task_json_path == tmp_path / "test_project__task.json"
        assert visualization_source_files.input_data_json_path == tmp_path / "test_project__input_data.json"

    def test_get_video_duration_minutes_by_task_id_with_data(self, visualization_source_files, tmp_path):
        """データありでの動画長さ計算テスト"""
        # テストデータを作成
        task_data = [{"task_id": "task1", "input_data_id_list": ["input1"]}, {"task_id": "task2", "input_data_id_list": ["input2"]}]

        input_data = [
            {
                "input_data_id": "input1",
                "system_metadata": {
                    "input_duration": 120.0  # 2分 = 120秒
                },
            },
            {
                "input_data_id": "input2",
                "system_metadata": {
                    "input_duration": 180.0  # 3分 = 180秒
                },
            },
        ]

        task_json_path = tmp_path / "test_project__task.json"
        input_data_json_path = tmp_path / "test_project__input_data.json"

        task_json_path.write_text(json.dumps(task_data), encoding="utf-8")
        input_data_json_path.write_text(json.dumps(input_data), encoding="utf-8")

        result = visualization_source_files.get_video_duration_minutes_by_task_id()

        # 期待値: 120秒 = 2分、180秒 = 3分
        expected = {"task1": 2.0, "task2": 3.0}
        assert result == expected


@pytest.mark.parametrize("with_annotation", [False, True])
def test_write_latest_files_submits_selected_updates_before_waiting(tmp_path, with_annotation):
    service = Mock()
    for name in ["post_project_tasks_update", "post_project_inputs_update", "post_annotation_archive_update"]:
        getattr(service.api, name).return_value = ({"job": {"job_id": "job"}}, None)

    def wait_for_job(*_args, **_kwargs):
        service.api.post_project_tasks_update.assert_called_once_with("p")
        service.api.post_project_inputs_update.assert_called_once_with("p")
        assert service.api.post_annotation_archive_update.call_count == (1 if with_annotation else 0)
        assert service.wrapper.download_project_tasks_json.call_count == 0
        return {"list": [{"job_id": "job", "job_status": JobStatus.SUCCEEDED.value}]}, None

    service.api.get_project_job.side_effect = wait_for_job
    for name in ["download_project_tasks_json", "download_project_inputs_json", "download_project_comments_json", "download_project_task_histories_json", "download_project_task_history_events_json"]:
        getattr(service.wrapper, name).side_effect = lambda _p, dest: Path(dest).write_text("[]", encoding="utf-8")
    service.wrapper.download_annotation_zip.side_effect = lambda _p, dest: Path(dest).write_bytes(b"archive")
    sources = VisualizationSourceFiles(service, "p", tmp_path)
    sources.write_files(is_latest=True, should_download_annotation_zip=with_annotation)
    assert json.loads(sources.task_json_path.read_text()) == []
    assert json.loads(sources.input_data_json_path.read_text()) == []
    assert sources.annotation_zip_path.exists() is with_annotation
    assert service.api.get_project_job.call_count == (3 if with_annotation else 2)
    assert service.api.post_project_tasks_update.call_count == 1
    assert service.api.post_project_inputs_update.call_count == 1
    assert service.api.post_annotation_archive_update.call_count == (1 if with_annotation else 0)
