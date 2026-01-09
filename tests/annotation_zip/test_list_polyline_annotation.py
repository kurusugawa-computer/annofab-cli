"""
Test cases for annofabcli.annotation_zip.list_polyline_annotation module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_polyline_annotation import calculate_polyline_properties, get_annotation_polyline_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestCalculatePolylineProperties:
    """calculate_polyline_properties関数のテストクラス"""

    def test_calculate_polyline_properties_with_multiple_points(self):
        """複数点のポリラインのプロパティ計算をテスト"""
        points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 20, "y": 10}]

        length, start_point, end_point, midpoint, bbox_width, bbox_height = calculate_polyline_properties(points)

        assert length is not None
        assert length == pytest.approx(30.0)  # 10 + 10 + 10 = 30
        assert start_point is not None
        assert start_point["x"] == pytest.approx(0.0)
        assert start_point["y"] == pytest.approx(0.0)
        assert end_point is not None
        assert end_point["x"] == pytest.approx(20.0)
        assert end_point["y"] == pytest.approx(10.0)
        assert midpoint is not None
        assert midpoint["x"] == pytest.approx(10.0)  # (0 + 10 + 10 + 20) / 4 = 10
        assert midpoint["y"] == pytest.approx(5.0)  # (0 + 0 + 10 + 10) / 4 = 5
        assert bbox_width == pytest.approx(20.0)
        assert bbox_height == pytest.approx(10.0)

    def test_calculate_polyline_properties_with_diagonal_line(self):
        """斜めの線のプロパティ計算をテスト"""
        points = [{"x": 0, "y": 0}, {"x": 3, "y": 4}]

        length, start_point, end_point, midpoint, bbox_width, bbox_height = calculate_polyline_properties(points)

        assert length is not None
        assert length == pytest.approx(5.0)  # 3-4-5の直角三角形
        assert start_point is not None
        assert start_point["x"] == pytest.approx(0.0)
        assert start_point["y"] == pytest.approx(0.0)
        assert end_point is not None
        assert end_point["x"] == pytest.approx(3.0)
        assert end_point["y"] == pytest.approx(4.0)
        assert midpoint is not None
        assert midpoint["x"] == pytest.approx(1.5)
        assert midpoint["y"] == pytest.approx(2.0)
        assert bbox_width == pytest.approx(3.0)
        assert bbox_height == pytest.approx(4.0)


class TestGetAnnotationPolylineInfoList:
    """get_annotation_polyline_info_list関数のテストクラス"""

    def test_get_annotation_polyline_info_list_basic(self):
        """基本的な動作をテスト：Points型のアノテーションを正しく抽出できるか"""
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
                    "label": "road",
                    "annotation_id": "line1",
                    "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]},
                    "attributes": {"type": "dashed", "color": "white"},
                },
                {
                    "label": "lane",
                    "annotation_id": "line2",
                    "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 3, "y": 4}]},
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_polyline_info_list(simple_annotation)

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
        assert first_annotation.label == "road"
        assert first_annotation.annotation_id == "line1"
        assert first_annotation.point_count == 3
        assert first_annotation.length == pytest.approx(20.0)
        assert first_annotation.start_point is not None
        assert first_annotation.start_point["x"] == pytest.approx(0.0)
        assert first_annotation.start_point["y"] == pytest.approx(0.0)
        assert first_annotation.end_point is not None
        assert first_annotation.end_point["x"] == pytest.approx(10.0)
        assert first_annotation.end_point["y"] == pytest.approx(10.0)
        assert first_annotation.midpoint is not None
        assert first_annotation.midpoint["x"] == pytest.approx(20.0 / 3)
        assert first_annotation.midpoint["y"] == pytest.approx(10.0 / 3)
        assert first_annotation.bounding_box_width == pytest.approx(10.0)
        assert first_annotation.bounding_box_height == pytest.approx(10.0)
        assert first_annotation.attributes == {"type": "dashed", "color": "white"}
        assert len(first_annotation.points) == 3

        # 2番目のアノテーション
        second_annotation = result[1]
        assert second_annotation.label == "lane"
        assert second_annotation.annotation_id == "line2"
        assert second_annotation.point_count == 2
        assert second_annotation.length == pytest.approx(5.0)
        assert second_annotation.start_point is not None
        assert second_annotation.start_point["x"] == pytest.approx(0.0)
        assert second_annotation.start_point["y"] == pytest.approx(0.0)
        assert second_annotation.end_point is not None
        assert second_annotation.end_point["x"] == pytest.approx(3.0)
        assert second_annotation.end_point["y"] == pytest.approx(4.0)
        assert second_annotation.midpoint is not None
        assert second_annotation.midpoint["x"] == pytest.approx(1.5)
        assert second_annotation.midpoint["y"] == pytest.approx(2.0)
        assert second_annotation.bounding_box_width == pytest.approx(3.0)
        assert second_annotation.bounding_box_height == pytest.approx(4.0)
        assert second_annotation.attributes == {}
        assert len(second_annotation.points) == 2

    def test_get_annotation_polyline_info_list_with_label_filter(self):
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
                {"label": "road", "annotation_id": "line1", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]}, "attributes": {}},
                {"label": "lane", "annotation_id": "line2", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 20, "y": 0}]}, "attributes": {}},
                {"label": "boundary", "annotation_id": "line3", "data": {"_type": "Points", "points": [{"x": 5, "y": 5}, {"x": 15, "y": 5}]}, "attributes": {}},
            ],
        }

        # roadとboundaryのみを取得
        result = get_annotation_polyline_info_list(simple_annotation, target_label_names=["road", "boundary"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "road" in labels
        assert "boundary" in labels
        assert "lane" not in labels

    def test_get_annotation_polyline_info_list_ignores_non_polyline(self):
        """Points型のアノテーション（ポリラインとポリゴン両方）が抽出され、BoundingBoxなどは無視されることをテスト"""
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
                {"label": "road", "annotation_id": "line1", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]}, "attributes": {}},
                {"label": "polygon", "annotation_id": "poly1", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]}, "attributes": {}},
                {"label": "bbox", "annotation_id": "bbox1", "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}}, "attributes": {}},
            ],
        }

        result = get_annotation_polyline_info_list(simple_annotation)

        # Points型のアノテーションはポリゴンも含めてすべて抽出される（Annofabの仕様上、ポリラインとポリゴンの区別がないため）
        assert len(result) == 2
        labels = [r.label for r in result]
        assert "road" in labels
        assert "polygon" in labels


@pytest.mark.access_webapi
class TestCommandLine:
    def test__list_polyline_annotation(self):
        main(
            [
                "annotation_zip",
                "list_polyline_annotation",
                "--annotation",
                str(data_dir / "image_annotation/"),
                "--output",
                str(out_dir / "list_polyline_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
