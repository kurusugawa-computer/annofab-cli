"""
Test cases for annofabcli.annotation_zip.list_range_annotation module
"""

from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.list_range_annotation import create_df, get_range_annotation_info_list

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
                {"label": "traffic_light", "annotation_id": "anno1", "data": {"_type": "Range", "begin": 5000, "end": 10000}, "attributes": {"color": "red", "occluded": False}},
                {"label": "person", "annotation_id": "anno2", "data": {"_type": "Range", "begin": 15000, "end": 20000}, "attributes": {"type": "adult"}},
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
        assert first_annotation.attributes == {"color": "red", "occluded": False}

        # 2番目のアノテーション
        second_annotation = result[1]
        assert second_annotation.label == "person"
        assert second_annotation.annotation_id == "anno2"
        assert second_annotation.begin_second == 15.0
        assert second_annotation.end_second == 20.0
        assert second_annotation.duration_second == 5.0
        assert second_annotation.attributes == {"type": "adult"}

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
                {"label": "traffic_light", "annotation_id": "anno1", "data": {"_type": "Range", "begin": 5000, "end": 10000}, "attributes": {"color": "red"}},
                {"label": "person", "annotation_id": "anno2", "data": {"_type": "Range", "begin": 15000, "end": 20000}, "attributes": {"type": "adult"}},
                {"label": "car", "annotation_id": "anno3", "data": {"_type": "Range", "begin": 25000, "end": 30000}, "attributes": {"type": "sedan"}},
            ],
        }

        # traffic_light と car のみを取得
        result = get_range_annotation_info_list(simple_annotation, target_label_names=["traffic_light", "car"])

        assert len(result) == 2
        labels = [annotation.label for annotation in result]
        assert "traffic_light" in labels
        assert "car" in labels
        assert "person" not in labels


class TestCreateDf:
    """create_df関数のテストクラス"""

    def test_create_df_with_empty_list(self):
        """空のリストで呼び出した場合に正しく空のDataFrameが返されることをテスト"""
        result = create_df([])

        assert result.empty
        # 基本列が存在することを確認
        expected_columns = [
            "project_id",
            "task_id",
            "task_status",
            "task_phase",
            "task_phase_stage",
            "input_data_id",
            "input_data_name",
            "updated_datetime",
            "label",
            "annotation_id",
            "begin_second",
            "end_second",
            "duration_second",
        ]
        assert list(result.columns) == expected_columns

    def test_create_df_with_attributes(self):
        """属性を持つアノテーションのリストで正しくDataFrameが生成されることをテスト"""
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
                {
                    "label": "traffic_light",
                    "annotation_id": "anno1",
                    "data": {"_type": "Range", "begin": 5000, "end": 10000},
                    "attributes": {"color": "red", "occluded": False, "type": "signal"},
                },
                {
                    "label": "person",
                    "annotation_id": "anno2",
                    "data": {"_type": "Range", "begin": 15000, "end": 20000},
                    "attributes": {"age": "adult", "occluded": True},
                },
            ],
        }

        annotation_list = get_range_annotation_info_list(simple_annotation)
        result = create_df(annotation_list)

        # データが2行あることを確認
        assert len(result) == 2

        # 基本列 + 属性列が存在することを確認
        expected_base_columns = [
            "project_id",
            "task_id",
            "task_status",
            "task_phase",
            "task_phase_stage",
            "input_data_id",
            "input_data_name",
            "updated_datetime",
            "label",
            "annotation_id",
            "begin_second",
            "end_second",
            "duration_second",
        ]

        # 属性列がアルファベット順にソートされていることを確認
        expected_attribute_columns = ["attributes.age", "attributes.color", "attributes.occluded", "attributes.type"]
        expected_columns = expected_base_columns + expected_attribute_columns

        assert list(result.columns) == expected_columns

        # 1行目のデータを確認
        assert result.iloc[0]["project_id"] == "test_project"
        assert result.iloc[0]["task_id"] == "test_task"
        assert result.iloc[0]["label"] == "traffic_light"
        assert result.iloc[0]["annotation_id"] == "anno1"
        assert result.iloc[0]["begin_second"] == 5.0
        assert result.iloc[0]["end_second"] == 10.0
        assert result.iloc[0]["duration_second"] == 5.0
        assert result.iloc[0]["attributes.color"] == "red"
        assert not result.iloc[0]["attributes.occluded"]
        assert result.iloc[0]["attributes.type"] == "signal"

        # 2行目のデータを確認
        assert result.iloc[1]["label"] == "person"
        assert result.iloc[1]["annotation_id"] == "anno2"
        assert result.iloc[1]["attributes.age"] == "adult"
        assert result.iloc[1]["attributes.occluded"]


@pytest.mark.access_webapi
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
