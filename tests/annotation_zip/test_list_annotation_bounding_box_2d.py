"""
Test cases for annofabcli.annotation_zip.list_annotation_bounding_box_2d module
"""

from __future__ import annotations

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_annotation_bounding_box_2d import get_annotation_bounding_box_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestGetAnnotationBoundingBoxInfoList:
    """get_annotation_bounding_box_info_list関数のテストクラス"""

    def test_get_annotation_bounding_box_info_list_basic(self):
        """基本的な動作をテスト：BoundingBox型のアノテーションを正しく抽出できるか"""
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
                {"label": "person", "annotation_id": "bbox1", "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}}, "attributes": {"key1": "value1"}},
                {"label": "car", "annotation_id": "bbox2", "data": {"_type": "BoundingBox", "left_top": {"x": 200, "y": 300}, "right_bottom": {"x": 400, "y": 500}}, "attributes": {}},
            ],
        }

        result = get_annotation_bounding_box_info_list(simple_annotation)

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
        assert first_annotation.label == "person"
        assert first_annotation.annotation_id == "bbox1"
        assert first_annotation.left_top == {"x": 10, "y": 20}
        assert first_annotation.right_bottom == {"x": 110, "y": 120}
        assert first_annotation.width == 100  # |110 - 10| = 100
        assert first_annotation.height == 100  # |120 - 20| = 100

        # 2番目のアノテーション
        second_annotation = result[1]
        assert second_annotation.label == "car"
        assert second_annotation.annotation_id == "bbox2"
        assert second_annotation.left_top == {"x": 200, "y": 300}
        assert second_annotation.right_bottom == {"x": 400, "y": 500}
        assert second_annotation.width == 200  # |400 - 200| = 200
        assert second_annotation.height == 200  # |500 - 300| = 200

    def test_get_annotation_bounding_box_info_list_with_label_filter(self):
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
                {"label": "person", "annotation_id": "bbox1", "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}}, "attributes": {}},
                {"label": "car", "annotation_id": "bbox2", "data": {"_type": "BoundingBox", "left_top": {"x": 200, "y": 300}, "right_bottom": {"x": 400, "y": 500}}, "attributes": {}},
                {"label": "bike", "annotation_id": "bbox3", "data": {"_type": "BoundingBox", "left_top": {"x": 50, "y": 60}, "right_bottom": {"x": 150, "y": 160}}, "attributes": {}},
            ],
        }

        # personとbikeのみを取得
        result = get_annotation_bounding_box_info_list(simple_annotation, target_label_names=["person", "bike"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "person" in labels
        assert "bike" in labels
        assert "car" not in labels


@pytest.mark.access_webapi
class TestCommandLine:
    def test__list_range_annotation(self):
        main(
            [
                "annotation_zip",
                "list_bounding_box_annotation",
                "--annotation",
                str(data_dir / "image_annotation/"),
                "--output",
                str(out_dir / "list_bounding_box_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
