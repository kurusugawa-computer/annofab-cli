"""
Test cases for annofabcli.annotation_zip.list_single_point_annotation module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_single_point_annotation import get_annotation_single_point_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestGetAnnotationSinglePointInfoList:
    """get_annotation_single_point_info_list関数のテストクラス"""

    def test_get_annotation_single_point_info_list_basic(self):
        """基本的な動作をテスト：SinglePoint型のアノテーションを正しく抽出できるか"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image.jpg",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "landmark", "annotation_id": "point1", "data": {"_type": "SinglePoint", "point": {"x": 100, "y": 200}}, "attributes": {"key1": "value1"}},
                {"label": "center", "annotation_id": "point2", "data": {"_type": "SinglePoint", "point": {"x": 50, "y": 75}}, "attributes": {}},
            ],
        }

        result = get_annotation_single_point_info_list(simple_annotation)

        assert len(result) == 2

        # 1番目のアノテーション
        first_annotation = result[0]
        assert first_annotation.project_id == "test_project"
        assert first_annotation.task_id == "test_task"
        assert first_annotation.task_phase == "annotation"
        assert first_annotation.task_phase_stage == 1
        assert first_annotation.task_status == "working"
        assert first_annotation.input_data_id == "test_image.jpg"
        assert first_annotation.input_data_name == "test_image.jpg"
        assert first_annotation.updated_datetime == "2023-01-01T00:00:00+09:00"
        assert first_annotation.label == "landmark"
        assert first_annotation.annotation_id == "point1"
        assert first_annotation.point == {"x": 100, "y": 200}

        # 2番目のアノテーション
        second_annotation = result[1]
        assert second_annotation.label == "center"
        assert second_annotation.annotation_id == "point2"
        assert second_annotation.point == {"x": 50, "y": 75}

    def test_get_annotation_single_point_info_list_with_label_filter(self):
        """target_label_names でフィルタリングが正しく機能するかテスト"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image.jpg",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "landmark", "annotation_id": "point1", "data": {"_type": "SinglePoint", "point": {"x": 100, "y": 200}}, "attributes": {}},
                {"label": "center", "annotation_id": "point2", "data": {"_type": "SinglePoint", "point": {"x": 50, "y": 75}}, "attributes": {}},
                {"label": "corner", "annotation_id": "point3", "data": {"_type": "SinglePoint", "point": {"x": 0, "y": 0}}, "attributes": {}},
            ],
        }

        # landmarkとcornerのみを取得
        result = get_annotation_single_point_info_list(simple_annotation, target_label_names=["landmark", "corner"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "landmark" in labels
        assert "corner" in labels
        assert "center" not in labels


@pytest.mark.access_webapi
class TestCommandLine:
    def test__list_single_point_annotation(self):
        main(
            [
                "annotation_zip",
                "list_single_point_annotation",
                "--annotation",
                str(data_dir / "image_annotation/"),
                "--output",
                str(out_dir / "list_single_point_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
