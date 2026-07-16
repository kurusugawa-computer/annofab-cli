"""
Test cases for annofabcli.annotation_zip.list_segmentation_annotation module
"""

from pathlib import Path

import numpy
import pytest
from annofabapi.segmentation import write_binary_image

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_segmentation_annotation import calculate_segmentation_properties, get_annotation_segmentation_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestCalculateSegmentationProperties:
    """calculate_segmentation_properties関数のテストクラス"""

    def test_calculate_segmentation_properties(self, tmp_path):
        """塗りつぶし画像の面積と外接矩形を計算できることをテスト"""
        binary_image_array = numpy.zeros((6, 8), dtype=bool)
        binary_image_array[2:5, 3:7] = True
        image_file = tmp_path / "segmentation.png"
        write_binary_image(binary_image_array, image_file)

        area, bounding_box, bounding_box_width, bounding_box_height = calculate_segmentation_properties(image_file)

        assert area == 12
        assert bounding_box == {
            "left_top": {"x": 3, "y": 2},
            "right_bottom": {"x": 6, "y": 4},
        }
        assert bounding_box_width == 4
        assert bounding_box_height == 3

    def test_calculate_segmentation_properties_empty(self, tmp_path):
        """塗りつぶし領域がない場合、外接矩形がNoneになることをテスト"""
        binary_image_array = numpy.zeros((6, 8), dtype=bool)
        image_file = tmp_path / "empty_segmentation.png"
        write_binary_image(binary_image_array, image_file)

        area, bounding_box, bounding_box_width, bounding_box_height = calculate_segmentation_properties(image_file)

        assert area == 0
        assert bounding_box is None
        assert bounding_box_width is None
        assert bounding_box_height is None


class TestGetAnnotationSegmentationInfoList:
    """get_annotation_segmentation_info_list関数のテストクラス"""

    def test_get_annotation_segmentation_info_list_basic(self):
        """基本的な動作をテスト：Segmentation型のアノテーションを正しく抽出できるか"""
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
                    "annotation_id": "seg1",
                    "data": {"_type": "Segmentation", "data_uri": "seg1.png"},
                    "attributes": {"visible": True},
                },
                {
                    "label": "building",
                    "annotation_id": "seg2",
                    "data": {"_type": "SegmentationV2", "data_uri": "seg2.png"},
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_segmentation_info_list(simple_annotation)

        assert len(result) == 2

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
        assert first_annotation.annotation_id == "seg1"
        assert first_annotation.annotation_type == "Segmentation"
        assert first_annotation.data_uri == "seg1.png"
        assert first_annotation.area is None
        assert first_annotation.bounding_box is None
        assert first_annotation.bounding_box_width is None
        assert first_annotation.bounding_box_height is None
        assert first_annotation.attributes == {"visible": True}

        second_annotation = result[1]
        assert second_annotation.label == "building"
        assert second_annotation.annotation_id == "seg2"
        assert second_annotation.annotation_type == "SegmentationV2"
        assert second_annotation.data_uri == "seg2.png"

    def test_get_annotation_segmentation_info_list_with_label_filter(self):
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
                {"label": "road", "annotation_id": "seg1", "data": {"_type": "Segmentation", "data_uri": "seg1.png"}, "attributes": {}},
                {"label": "building", "annotation_id": "seg2", "data": {"_type": "SegmentationV2", "data_uri": "seg2.png"}, "attributes": {}},
                {"label": "sky", "annotation_id": "seg3", "data": {"_type": "SegmentationV2", "data_uri": "seg3.png"}, "attributes": {}},
            ],
        }

        result = get_annotation_segmentation_info_list(simple_annotation, target_label_names=["road", "sky"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "road" in labels
        assert "sky" in labels
        assert "building" not in labels

    def test_get_annotation_segmentation_info_list_with_outer_file(self, tmp_path):
        """外部ファイルを読み込んで面積と外接矩形を設定できることをテスト"""
        binary_image_array = numpy.zeros((6, 8), dtype=bool)
        binary_image_array[2:5, 3:7] = True
        image_file = tmp_path / "segmentation.png"
        write_binary_image(binary_image_array, image_file)
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
                {"label": "road", "annotation_id": "seg1", "data": {"_type": "Segmentation", "data_uri": "seg1.png"}, "attributes": {}},
            ],
        }

        result = get_annotation_segmentation_info_list(simple_annotation, open_outer_file=lambda _: image_file)

        assert len(result) == 1
        assert result[0].area == 12
        assert result[0].bounding_box == {
            "left_top": {"x": 3, "y": 2},
            "right_bottom": {"x": 6, "y": 4},
        }
        assert result[0].bounding_box_width == 4
        assert result[0].bounding_box_height == 3

    def test_get_annotation_segmentation_info_list_ignores_non_segmentation(self):
        """塗りつぶし以外のアノテーションは無視されることをテスト"""
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
                {"label": "road", "annotation_id": "seg1", "data": {"_type": "Segmentation", "data_uri": "seg1.png"}, "attributes": {}},
                {"label": "point", "annotation_id": "point1", "data": {"_type": "SinglePoint", "point": {"x": 50, "y": 50}}, "attributes": {}},
            ],
        }

        result = get_annotation_segmentation_info_list(simple_annotation)

        assert len(result) == 1
        assert result[0].label == "road"


@pytest.mark.access_webapi
class TestCommandLine:
    def test__list_segmentation_annotation(self):
        main(
            [
                "annotation_zip",
                "list_segmentation_annotation",
                "--annotation",
                str(data_dir / "image_annotation/"),
                "--output",
                str(out_dir / "list_segmentation_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
