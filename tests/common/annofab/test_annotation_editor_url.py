"""
Test cases for annofabcli.common.annofab.annotation_editor_url module
"""

from __future__ import annotations

from annofabcli.common.annofab.annotation_editor_url import create_annotation_editor_url, get_annotation_editor_type_from_input_data_type


def test_get_annotation_editor_type_from_input_data_type():
    assert get_annotation_editor_type_from_input_data_type("image") == "image"
    assert get_annotation_editor_type_from_input_data_type("movie") == "video"
    assert get_annotation_editor_type_from_input_data_type("custom") == "3dpc"


def test_create_annotation_editor_url_has_video_editor_url_for_range_annotation():
    simple_annotation = {
        "project_id": "test_project",
        "task_id": "test_task",
        "input_data_id": "test_video",
    }
    detail = {
        "annotation_id": "annotation1",
        "data": {"_type": "Range", "begin": 1500, "end": 3000},
    }

    result = create_annotation_editor_url(simple_annotation, detail)

    assert result == "https://annofab.com/projects/test_project/tasks/test_task/timeline?#annotation1/1.5"
