"""
Test cases for annofabcli.annotation_zip.list_classification_annotation module
"""

from __future__ import annotations

from pathlib import Path

import pandas

from annofabcli.annotation_zip.list_classification_annotation import (
    create_df,
    get_annotation_editor_type_from_input_data_type,
    get_classification_annotation_info_list,
)


class TestGetClassificationAnnotationInfoList:
    """get_classification_annotation_info_list関数のテストクラス"""

    def test_get_classification_annotation_info_list_basic(self):
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "scene", "annotation_id": "classification1", "data": {"_type": "Classification"}, "attributes": {"weather": "sunny"}},
                {"label": "person", "annotation_id": "box1", "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}}, "attributes": {}},
            ],
        }

        result = get_classification_annotation_info_list(simple_annotation)

        assert len(result) == 1
        classification_annotation = result[0]
        assert classification_annotation.project_id == "test_project"
        assert classification_annotation.task_id == "test_task"
        assert classification_annotation.task_phase == "annotation"
        assert classification_annotation.task_phase_stage == 1
        assert classification_annotation.task_status == "working"
        assert classification_annotation.input_data_id == "test_image"
        assert classification_annotation.input_data_name == "test_image.jpg"
        assert classification_annotation.updated_datetime == "2023-01-01T00:00:00+09:00"
        assert classification_annotation.label == "scene"
        assert classification_annotation.annotation_id == "classification1"
        assert classification_annotation.annotation_editor_url == "https://annofab.com/projects/test_project/tasks/test_task/editor?#test_image/classification1"
        assert classification_annotation.attributes == {"weather": "sunny"}

    def test_get_classification_annotation_info_list_with_label_filter(self):
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "scene", "annotation_id": "classification1", "data": {"_type": "Classification"}, "attributes": {}},
                {"label": "quality", "annotation_id": "classification2", "data": {"_type": "Classification"}, "attributes": {}},
            ],
        }

        result = get_classification_annotation_info_list(simple_annotation, target_label_names=["quality"])

        assert len(result) == 1
        assert result[0].label == "quality"

    def test_get_classification_annotation_info_list_uses_video_editor_url_by_annotation_editor_type(self):
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_video",
            "input_data_name": "test_video.mp4",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "scene", "annotation_id": "classification1", "data": {"_type": "Classification"}, "attributes": {"weather": "sunny"}},
            ],
        }

        result = get_classification_annotation_info_list(simple_annotation, annotation_editor_type="video")

        assert len(result) == 1
        assert result[0].annotation_editor_url == "https://annofab.com/projects/test_project/tasks/test_task/timeline?#classification1"


def test_get_annotation_editor_type_from_input_data_type():
    assert get_annotation_editor_type_from_input_data_type("image") == "image"
    assert get_annotation_editor_type_from_input_data_type("movie") == "video"
    assert get_annotation_editor_type_from_input_data_type("custom") == "3dpc"


class TestCreateDf:
    """create_df関数のテストクラス"""

    def test_create_df_with_empty_list(self):
        result = create_df([])

        assert result.empty
        assert list(result.columns) == [
            "project_id",
            "task_id",
            "task_phase",
            "task_phase_stage",
            "task_status",
            "input_data_id",
            "input_data_name",
            "updated_datetime",
            "label",
            "annotation_id",
            "annotation_editor_url",
        ]

    def test_create_df_with_attributes(self, tmp_path: Path):
        simple_annotation = {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "task_status": "working",
            "input_data_id": "test_image",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "details": [
                {"label": "scene", "annotation_id": "classification1", "data": {"_type": "Classification"}, "attributes": {"weather": "sunny"}},
            ],
        }
        output_file = tmp_path / "out.csv"

        df = create_df(get_classification_annotation_info_list(simple_annotation))
        df.to_csv(output_file, index=False)
        actual_df = pandas.read_csv(output_file)

        assert "attributes.weather" in actual_df.columns
        assert actual_df.loc[0, "attributes.weather"] == "sunny"
