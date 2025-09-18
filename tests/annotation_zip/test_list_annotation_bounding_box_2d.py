"""
Test cases for annofabcli.annotation_zip.list_annotation_bounding_box_2d module
"""
from __future__ import annotations

import pytest

from annofabcli.annotation_zip.list_annotation_bounding_box_2d import get_annotation_bounding_box_info_list, AnnotationBoundingBoxInfo


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
                {
                    "label": "person",
                    "annotation_id": "bbox1",
                    "data": {
                        "_type": "BoundingBox",
                        "left_top": {"x": 10, "y": 20},
                        "right_bottom": {"x": 110, "y": 120}
                    }
                },
                {
                    "label": "car",
                    "annotation_id": "bbox2",
                    "data": {
                        "_type": "BoundingBox",
                        "left_top": {"x": 200, "y": 300},
                        "right_bottom": {"x": 400, "y": 500}
                    }
                }
            ]
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

    def test_get_annotation_bounding_box_info_list_no_bounding_box(self):
        """BoundingBox型以外のアノテーションのみの場合"""
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
                {
                    "label": "weather",
                    "annotation_id": "class1",
                    "data": {
                        "_type": "Classification"
                    }
                }
            ]
        }

        result = get_annotation_bounding_box_info_list(simple_annotation)

        assert len(result) == 0

    def test_get_annotation_bounding_box_info_list_empty_details(self):
        """details が空の場合"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image.jpg",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": []
        }

        result = get_annotation_bounding_box_info_list(simple_annotation)

        assert len(result) == 0