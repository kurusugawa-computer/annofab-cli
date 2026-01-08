"""
Test cases for annofabcli.annotation_zip.list_polygon_annotation module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_polygon_annotation import calculate_polygon_properties, get_annotation_polygon_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestCalculatePolygonProperties:
    """calculate_polygon_properties関数のテストクラス"""

    def test_calculate_polygon_properties_with_triangle(self):
        """三角形のポリゴンのプロパティ計算をテスト"""
        points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]

        area, centroid, bbox_width, bbox_height = calculate_polygon_properties(points)

        assert area is not None
        assert area == pytest.approx(50.0)  # 三角形の面積 = (10 * 10) / 2 = 50
        assert centroid is not None
        assert centroid["x"] == pytest.approx(10 / 3)
        assert centroid["y"] == pytest.approx(10 / 3)
        assert bbox_width == pytest.approx(10.0)
        assert bbox_height == pytest.approx(10.0)

    def test_calculate_polygon_properties_with_rectangle(self):
        """矩形のポリゴンのプロパティ計算をテスト"""
        points = [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10}, {"x": 0, "y": 10}]

        area, centroid, bbox_width, bbox_height = calculate_polygon_properties(points)

        assert area is not None
        assert area == pytest.approx(200.0)  # 矩形の面積 = 20 * 10 = 200
        assert centroid is not None
        assert centroid["x"] == pytest.approx(10.0)
        assert centroid["y"] == pytest.approx(5.0)
        assert bbox_width == pytest.approx(20.0)
        assert bbox_height == pytest.approx(10.0)

    def test_calculate_polygon_properties_with_two_points(self):
        """2点のポリライン（ポリゴンではない）の場合はNoneを返すことをテスト"""
        points = [{"x": 0, "y": 0}, {"x": 10, "y": 10}]

        area, centroid, bbox_width, bbox_height = calculate_polygon_properties(points)

        assert area is None
        assert centroid is None
        assert bbox_width is None
        assert bbox_height is None

    def test_calculate_polygon_properties_with_one_point(self):
        """1点の場合はNoneを返すことをテスト"""
        points = [{"x": 0, "y": 0}]

        area, centroid, bbox_width, bbox_height = calculate_polygon_properties(points)

        assert area is None
        assert centroid is None
        assert bbox_width is None
        assert bbox_height is None


class TestGetAnnotationPolygonInfoList:
    """get_annotation_polygon_info_list関数のテストクラス"""

    def test_get_annotation_polygon_info_list_basic(self):
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
                    "label": "triangle",
                    "annotation_id": "poly1",
                    "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]},
                    "attributes": {"occluded": True, "type": "test"},
                },
                {
                    "label": "square",
                    "annotation_id": "poly2",
                    "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}]},
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_polygon_info_list(simple_annotation)

        assert len(result) == 2

        # 1番目のアノテーション（三角形）
        first_annotation = result[0]
        assert first_annotation.project_id == "test_project"
        assert first_annotation.task_id == "test_task"
        assert first_annotation.task_phase == "annotation"
        assert first_annotation.task_phase_stage == 1
        assert first_annotation.task_status == "working"
        assert first_annotation.input_data_id == "test_image.jpg"
        assert first_annotation.input_data_name == "test_image.jpg"
        assert first_annotation.updated_datetime == "2023-01-01T00:00:00+09:00"
        assert first_annotation.label == "triangle"
        assert first_annotation.annotation_id == "poly1"
        assert first_annotation.point_count == 3
        assert first_annotation.area == pytest.approx(50.0)
        assert first_annotation.centroid is not None
        assert first_annotation.centroid["x"] == pytest.approx(10 / 3)
        assert first_annotation.centroid["y"] == pytest.approx(10 / 3)
        assert first_annotation.bounding_box_width == pytest.approx(10.0)
        assert first_annotation.bounding_box_height == pytest.approx(10.0)
        assert first_annotation.attributes == {"occluded": True, "type": "test"}
        assert len(first_annotation.points) == 3

        # 2番目のアノテーション（正方形）
        second_annotation = result[1]
        assert second_annotation.label == "square"
        assert second_annotation.annotation_id == "poly2"
        assert second_annotation.point_count == 4
        assert second_annotation.area == pytest.approx(400.0)
        assert second_annotation.centroid is not None
        assert second_annotation.centroid["x"] == pytest.approx(10.0)
        assert second_annotation.centroid["y"] == pytest.approx(10.0)
        assert second_annotation.bounding_box_width == pytest.approx(20.0)
        assert second_annotation.bounding_box_height == pytest.approx(20.0)
        assert second_annotation.attributes == {}
        assert len(second_annotation.points) == 4

    def test_get_annotation_polygon_info_list_with_polyline(self):
        """2点のポリラインの場合、プロパティがNoneになることをテスト"""
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
                    "label": "line",
                    "annotation_id": "line1",
                    "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 10}]},
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_polygon_info_list(simple_annotation)

        assert len(result) == 1

        annotation = result[0]
        assert annotation.label == "line"
        assert annotation.point_count == 2
        assert annotation.area is None
        assert annotation.centroid is None
        assert annotation.bounding_box_width is None
        assert annotation.bounding_box_height is None
        assert len(annotation.points) == 2

    def test_get_annotation_polygon_info_list_with_label_filter(self):
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
                {"label": "triangle", "annotation_id": "poly1", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]}, "attributes": {}},
                {"label": "square", "annotation_id": "poly2", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}]}, "attributes": {}},
                {"label": "circle", "annotation_id": "poly3", "data": {"_type": "Points", "points": [{"x": 5, "y": 5}, {"x": 15, "y": 5}, {"x": 10, "y": 15}]}, "attributes": {}},
            ],
        }

        # triangleとcircleのみを取得
        result = get_annotation_polygon_info_list(simple_annotation, target_label_names=["triangle", "circle"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "triangle" in labels
        assert "circle" in labels
        assert "square" not in labels

    def test_get_annotation_polygon_info_list_ignores_non_points(self):
        """Points型以外のアノテーション（BoundingBox、SinglePointなど）は無視されることをテスト"""
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
                {"label": "triangle", "annotation_id": "poly1", "data": {"_type": "Points", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]}, "attributes": {}},
                {"label": "bbox", "annotation_id": "bbox1", "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}}, "attributes": {}},
                {"label": "point", "annotation_id": "point1", "data": {"_type": "SinglePoint", "point": {"x": 50, "y": 50}}, "attributes": {}},
            ],
        }

        result = get_annotation_polygon_info_list(simple_annotation)

        # Points型のアノテーションのみが抽出される
        assert len(result) == 1
        assert result[0].label == "triangle"


@pytest.mark.access_webapi
class TestCommandLine:
    def test__list_polygon_annotation(self):
        main(
            [
                "annotation_zip",
                "list_polygon_annotation",
                "--annotation",
                str(data_dir / "image_annotation/"),
                "--output",
                str(out_dir / "list_polygon_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
