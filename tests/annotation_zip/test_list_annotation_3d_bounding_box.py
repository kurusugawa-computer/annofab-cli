"""
Test cases for annofabcli.annotation_zip.list_annotation_3d_bounding_box module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_annotation_3d_bounding_box import get_annotation_3d_bounding_box_info_list

out_dir = Path("tests/out/annotation_zip")
data_dir = Path("tests/data/annotation_zip")


class TestGetAnnotation3DBoundingBoxInfoList:
    """get_annotation_3d_bounding_box_info_list関数のテストクラス"""

    def test_get_annotation_3d_bounding_box_info_list_basic(self):
        """基本的な動作をテスト：CUBOID型のアノテーションを正しく抽出できるか"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_pointcloud.bin",
            "input_data_name": "test_pointcloud.bin",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {
                    "label": "Car",
                    "annotation_id": "cuboid1",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":1.867,"height":1.673,"depth":4.629},"location":{"x":-7.878,"y":36.813,"z":0.208},"rotation":{"x":0,"y":0,"z":4.746},"direction":{"front":{"x":0.033,"y":-0.999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
                {
                    "label": "Pedestrian",
                    "annotation_id": "cuboid2",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":0.824,"height":1.917,"depth":1.259},"location":{"x":-20.534,"y":32.382,"z":-0.270},"rotation":{"x":0,"y":0,"z":4.701},"direction":{"front":{"x":-0.011,"y":-0.9999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_3d_bounding_box_info_list(simple_annotation)

        assert len(result) == 2

        # 1番目のアノテーション（Car）
        first_annotation = result[0]
        assert first_annotation.project_id == "test_project"
        assert first_annotation.task_id == "test_task"
        assert first_annotation.task_phase == "annotation"
        assert first_annotation.task_phase_stage == 1
        assert first_annotation.task_status == "working"
        assert first_annotation.input_data_id == "test_pointcloud.bin"
        assert first_annotation.input_data_name == "test_pointcloud.bin"
        assert first_annotation.updated_datetime == "2023-01-01T00:00:00+09:00"
        assert first_annotation.label == "Car"
        assert first_annotation.annotation_id == "cuboid1"
        assert first_annotation.dimensions["width"] == 1.867
        assert first_annotation.dimensions["height"] == 1.673
        assert first_annotation.dimensions["depth"] == 4.629
        assert first_annotation.location["x"] == -7.878
        assert first_annotation.location["y"] == 36.813
        assert first_annotation.location["z"] == 0.208
        # volume = width × height × depth
        assert first_annotation.volume == pytest.approx(1.867 * 1.673 * 4.629, rel=1e-3)
        # footprint_area = width × depth
        assert first_annotation.footprint_area == pytest.approx(1.867 * 4.629, rel=1e-3)
        # bottom_z = location.z - height/2
        assert first_annotation.bottom_z == pytest.approx(0.208 - 1.673 / 2, rel=1e-3)
        # top_z = location.z + height/2
        assert first_annotation.top_z == pytest.approx(0.208 + 1.673 / 2, rel=1e-3)

        # 2番目のアノテーション（Pedestrian）
        second_annotation = result[1]
        assert second_annotation.label == "Pedestrian"
        assert second_annotation.annotation_id == "cuboid2"
        assert second_annotation.dimensions["width"] == 0.824
        assert second_annotation.dimensions["height"] == 1.917
        assert second_annotation.dimensions["depth"] == 1.259
        assert second_annotation.volume == pytest.approx(0.824 * 1.917 * 1.259, rel=1e-3)
        assert second_annotation.footprint_area == pytest.approx(0.824 * 1.259, rel=1e-3)

    def test_get_annotation_3d_bounding_box_info_list_with_label_filter(self):
        """target_label_names でフィルタリングが正しく機能するかテスト"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_pointcloud.bin",
            "input_data_name": "test_pointcloud.bin",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {
                    "label": "Car",
                    "annotation_id": "cuboid1",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":1.867,"height":1.673,"depth":4.629},"location":{"x":-7.878,"y":36.813,"z":0.208},"rotation":{"x":0,"y":0,"z":4.746},"direction":{"front":{"x":0.033,"y":-0.999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
                {
                    "label": "Pedestrian",
                    "annotation_id": "cuboid2",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":0.824,"height":1.917,"depth":1.259},"location":{"x":-20.534,"y":32.382,"z":-0.270},"rotation":{"x":0,"y":0,"z":4.701},"direction":{"front":{"x":-0.011,"y":-0.9999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
                {
                    "label": "Truck",
                    "annotation_id": "cuboid3",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":2.5,"height":2.8,"depth":8.0},"location":{"x":10.0,"y":20.0,"z":1.0},"rotation":{"x":0,"y":0,"z":0},"direction":{"front":{"x":1,"y":0,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
            ],
        }

        # CarとTruckのみを取得
        result = get_annotation_3d_bounding_box_info_list(simple_annotation, target_label_names=["Car", "Truck"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "Car" in labels
        assert "Truck" in labels
        assert "Pedestrian" not in labels

    def test_get_annotation_3d_bounding_box_info_list_skip_non_cuboid(self):
        """CUBOID以外のアノテーションは無視されることをテスト"""
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_pointcloud.bin",
            "input_data_name": "test_pointcloud.bin",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {
                    "label": "Car",
                    "annotation_id": "cuboid1",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":1.867,"height":1.673,"depth":4.629},"location":{"x":-7.878,"y":36.813,"z":0.208},"rotation":{"x":0,"y":0,"z":4.746},"direction":{"front":{"x":0.033,"y":-0.999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
                {
                    "label": "Road",
                    "annotation_id": "segment1",
                    "data": {"data": "./001-0/segment1", "_type": "Unknown"},
                    "attributes": {},
                },
            ],
        }

        result = get_annotation_3d_bounding_box_info_list(simple_annotation)

        # CUBOIDのみが抽出される
        assert len(result) == 1
        assert result[0].label == "Car"


@pytest.mark.access_webapi
class TestCommandLine:
    def test_list_3d_bounding_box_annotation(self):
        """コマンドライン実行のテスト"""
        main(
            [
                "annotation_zip",
                "list_3d_bounding_box_annotation",
                "--annotation",
                str(data_dir / "3dpc-annotation/"),
                "--output",
                str(out_dir / "list_3d_bounding_box_annotation-out.json"),
                "--format",
                "pretty_json",
            ]
        )
