"""
Test cases for annofabcli.annotation_zip.list_range_annotation module
"""

from pathlib import Path

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_range_annotation import get_range_annotation_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestGetRangeAnnotationInfoList:
    """get_range_annotation_info_list関数のテストクラス"""

    def test_get_range_annotation_info_list_basic(self):
        """基本的な動作をテスト：Range型のアノテーションを正しく抽出できるか"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_video.mp4",
            "input_data_name": "test_video.mp4",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "traffic_light", "annotation_id": "anno1", "data": {"_type": "Range", "begin": 5000, "end": 10000}},
                {"label": "person", "annotation_id": "anno2", "data": {"_type": "Range", "begin": 15000, "end": 20000}},
            ],
        }

        result = get_range_annotation_info_list(simple_annotation)

        assert len(result) == 2

        # 1番目のアノテーション
        first_annotation = result[0]
        assert first_annotation.project_id == "test_project"
        assert first_annotation.task_id == "test_task"
        assert first_annotation.task_phase == "annotation"
        assert first_annotation.task_phase_stage == 1
        assert first_annotation.task_status == "working"
        assert first_annotation.input_data_id == "test_video.mp4"
        assert first_annotation.input_data_name == "test_video.mp4"
        assert first_annotation.updated_datetime == "2023-01-01T00:00:00+09:00"
        assert first_annotation.label == "traffic_light"
        assert first_annotation.annotation_id == "anno1"
        assert first_annotation.begin_second == 5.0
        assert first_annotation.end_second == 10.0
        assert first_annotation.duration_second == 5.0

        # 2番目のアノテーション
        second_annotation = result[1]
        assert second_annotation.label == "person"
        assert second_annotation.annotation_id == "anno2"
        assert second_annotation.begin_second == 15.0
        assert second_annotation.end_second == 20.0
        assert second_annotation.duration_second == 5.0

    def test_get_range_annotation_info_list_with_label_filter(self):
        """target_label_names でフィルタリングが正しく機能するかテスト"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_video.mp4",
            "input_data_name": "test_video.mp4",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "traffic_light", "annotation_id": "anno1", "data": {"_type": "Range", "begin": 5000, "end": 10000}},
                {"label": "person", "annotation_id": "anno2", "data": {"_type": "Range", "begin": 15000, "end": 20000}},
                {"label": "car", "annotation_id": "anno3", "data": {"_type": "Range", "begin": 25000, "end": 30000}},
            ],
        }

        # traffic_light と car のみを取得
        result = get_range_annotation_info_list(simple_annotation, target_label_names=["traffic_light", "car"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "traffic_light" in labels
        assert "car" in labels
        assert "person" not in labels


class TestCommandLine:
    def test__list_range_annotation(self):
        main(
            [
                "annotation_zip",
                "list_range_annotation",
                "--annotation",
                str(data_dir / "video_annotation/"),
                "--output",
                str(out_dir / "list_range_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
