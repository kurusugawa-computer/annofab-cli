"""
Test cases for annofabcli.annotation_zip.list_annotation_3d_bounding_box module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_annotation_3d_bounding_box import create_df, get_annotation_3d_bounding_box_info_list

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

    def test_get_annotation_3d_bounding_box_info_list_with_attributes(self):
        """属性値が設定されているアノテーションを正しく取得できるかテスト"""
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
                    "attributes": {"occluded": True, "type": "sedan", "count": 1},
                },
                {
                    "label": "Pedestrian",
                    "annotation_id": "cuboid2",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":0.824,"height":1.917,"depth":1.259},"location":{"x":-20.534,"y":32.382,"z":-0.270},"rotation":{"x":0,"y":0,"z":4.701},"direction":{"front":{"x":-0.011,"y":-0.9999,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {"occluded": False, "age": "adult"},
                },
            ],
        }

        result = get_annotation_3d_bounding_box_info_list(simple_annotation)

        assert len(result) == 2

        # 1番目のアノテーション（Car）の属性確認
        first_annotation = result[0]
        assert first_annotation.attributes == {"occluded": True, "type": "sedan", "count": 1}
        assert first_annotation.attributes["occluded"] is True
        assert first_annotation.attributes["type"] == "sedan"
        assert first_annotation.attributes["count"] == 1

        # 2番目のアノテーション（Pedestrian）の属性確認
        second_annotation = result[1]
        assert second_annotation.attributes == {"occluded": False, "age": "adult"}
        assert second_annotation.attributes["occluded"] is False
        assert second_annotation.attributes["age"] == "adult"


class TestCreateDf:
    """create_df関数のテストクラス"""

    def test_create_df_with_attributes(self):
        """属性情報が含まれる場合、CSV形式で属性列が正しく追加されることをテスト"""
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
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":1.5,"height":1.5,"depth":3.0},"location":{"x":0.0,"y":0.0,"z":0.0},"rotation":{"x":0,"y":0,"z":0},"direction":{"front":{"x":1,"y":0,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {"occluded": True, "type": "sedan"},
                },
                {
                    "label": "Truck",
                    "annotation_id": "cuboid2",
                    "data": {
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":2.0,"height":2.5,"depth":5.0},"location":{"x":10.0,"y":20.0,"z":1.0},"rotation":{"x":0,"y":0,"z":0},"direction":{"front":{"x":1,"y":0,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {"occluded": False, "type": "delivery"},
                },
            ],
        }

        annotation_list = get_annotation_3d_bounding_box_info_list(simple_annotation)
        df = create_df(annotation_list)

        # 基本列が存在することを確認
        assert "project_id" in df.columns
        assert "task_id" in df.columns
        assert "label" in df.columns
        assert "annotation_id" in df.columns
        assert "dimensions.width" in df.columns
        assert "volume" in df.columns

        # 属性列が存在することを確認
        assert "attributes.occluded" in df.columns
        assert "attributes.type" in df.columns

        # データの内容を確認
        assert len(df) == 2
        assert df.iloc[0]["label"] == "Car"
        assert df.iloc[0]["attributes.occluded"]
        assert df.iloc[0]["attributes.type"] == "sedan"

        assert df.iloc[1]["label"] == "Truck"
        assert not df.iloc[1]["attributes.occluded"]
        assert df.iloc[1]["attributes.type"] == "delivery"

    def test_create_df_empty_list(self):
        """空のリストの場合でもヘッダ行が出力されることをテスト"""
        annotation_list: list = []
        df = create_df(annotation_list)

        # DataFrameは空だが、base_columnsの列は存在する
        assert len(df) == 0
        assert len(df.columns) == 23  # base_columnsの数

        # 基本列が存在することを確認
        assert "project_id" in df.columns
        assert "task_id" in df.columns
        assert "label" in df.columns
        assert "dimensions.width" in df.columns
        assert "volume" in df.columns

        # 属性列は存在しない（データがないため）
        assert "attributes.occluded" not in df.columns

    def test_create_df_without_attributes(self):
        """属性がない場合、属性列が追加されないことをテスト"""
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
                        "data": '{"kind":"CUBOID","shape":{"dimensions":{"width":1.5,"height":1.5,"depth":3.0},"location":{"x":0.0,"y":0.0,"z":0.0},"rotation":{"x":0,"y":0,"z":0},"direction":{"front":{"x":1,"y":0,"z":0},"up":{"x":0,"y":0,"z":1}}},"version":"2"}',
                        "_type": "Unknown",
                    },
                    "attributes": {},
                },
            ],
        }

        annotation_list = get_annotation_3d_bounding_box_info_list(simple_annotation)
        df = create_df(annotation_list)

        # 基本列のみ存在し、属性列は存在しない
        assert len(df) == 1
        assert "project_id" in df.columns
        assert "label" in df.columns
        # 属性が空なので、attributes.xxxの列は追加されない
        attribute_columns = [col for col in df.columns if col.startswith("attributes.")]
        assert len(attribute_columns) == 0


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
