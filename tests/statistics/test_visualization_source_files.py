import json
from unittest.mock import Mock

import pytest

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
