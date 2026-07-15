"""
Test cases for annofabcli.annotation_zip.list_annotation_attribute module
"""

from __future__ import annotations

from pathlib import Path

import pandas

from annofabcli.annotation_zip.list_annotation_attribute import get_annotation_attribute_list_from_annotation_json, print_annotation_attribute_list_as_csv


def test_get_annotation_attribute_list_from_annotation_json_has_image_editor_url():
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
            {
                "label": "person",
                "annotation_id": "annotation1",
                "data": {"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 110, "y": 120}},
                "attributes": {"occluded": False},
            }
        ],
    }

    result = get_annotation_attribute_list_from_annotation_json(simple_annotation)

    assert len(result) == 1
    assert result[0].annotation_editor_url == "https://annofab.com/projects/test_project/tasks/test_task/editor?#test_image/annotation1"


def test_get_annotation_attribute_list_from_annotation_json_has_video_editor_url_for_range_annotation():
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
            {
                "label": "person",
                "annotation_id": "annotation1",
                "data": {"_type": "Range", "begin": 1500, "end": 3000},
                "attributes": {"occluded": False},
            }
        ],
    }

    result = get_annotation_attribute_list_from_annotation_json(simple_annotation)

    assert len(result) == 1
    assert result[0].annotation_editor_url == "https://annofab.com/projects/test_project/tasks/test_task/timeline?#annotation1/1.5"


def test_get_annotation_attribute_list_from_annotation_json_uses_video_editor_url_by_annotation_editor_type():
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
            {
                "label": "scene",
                "annotation_id": "annotation1",
                "data": {"_type": "Classification"},
                "attributes": {"weather": "sunny"},
            }
        ],
    }

    result = get_annotation_attribute_list_from_annotation_json(simple_annotation, annotation_editor_type="video")

    assert len(result) == 1
    assert result[0].annotation_editor_url == "https://annofab.com/projects/test_project/tasks/test_task/timeline?#annotation1"


def test_get_annotation_attribute_list_from_annotation_json_has_3dpc_editor_url_for_unknown_annotation():
    simple_annotation = {
        "project_id": "test_project",
        "task_id": "test_task",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "working",
        "input_data_id": "test_point_cloud",
        "input_data_name": "test_point_cloud.bin",
        "updated_datetime": "2023-01-01T00:00:00+09:00",
        "details": [
            {
                "label": "car",
                "annotation_id": "annotation1",
                "data": {"_type": "Unknown", "data": '{"kind":"CUBOID","version":"2"}'},
                "attributes": {"occluded": False},
            }
        ],
    }

    result = get_annotation_attribute_list_from_annotation_json(simple_annotation)

    assert len(result) == 1
    assert result[0].annotation_editor_url == "https://d2rljy8mjgrfyd.cloudfront.net/3d-editor-latest/index.html?p=test_project&t=test_task#/test_point_cloud/annotation1"


def test_get_annotation_attribute_list_from_annotation_json_uses_3dpc_editor_url_by_annotation_editor_type():
    simple_annotation = {
        "project_id": "test_project",
        "task_id": "test_task",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "working",
        "input_data_id": "test_point_cloud",
        "input_data_name": "test_point_cloud.bin",
        "updated_datetime": "2023-01-01T00:00:00+09:00",
        "details": [
            {
                "label": "car",
                "annotation_id": "annotation1",
                "data": {"_type": "Unknown", "data": '{"kind":"CUBOID","version":"2"}'},
                "attributes": {"occluded": False},
            }
        ],
    }

    result = get_annotation_attribute_list_from_annotation_json(simple_annotation, annotation_editor_type="3dpc")

    assert len(result) == 1
    assert result[0].annotation_editor_url == "https://d2rljy8mjgrfyd.cloudfront.net/3d-editor-latest/index.html?p=test_project&t=test_task#/test_point_cloud/annotation1"


def test_print_annotation_attribute_list_as_csv_has_annotation_editor_url_column(tmp_path: Path):
    output_file = tmp_path / "out.csv"
    annotation_attribute_list = [
        {
            "project_id": "test_project",
            "task_id": "test_task",
            "task_status": "working",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "input_data_id": "test_image",
            "input_data_name": "test_image.jpg",
            "updated_datetime": "2023-01-01T00:00:00+09:00",
            "annotation_id": "annotation1",
            "annotation_editor_url": "https://annofab.com/projects/test_project/tasks/test_task/editor?#test_image/annotation1",
            "label": "person",
            "attributes": {"occluded": False},
        }
    ]

    print_annotation_attribute_list_as_csv(annotation_attribute_list, output_file)

    df = pandas.read_csv(output_file)
    assert list(df.columns) == [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "annotation_id",
        "annotation_editor_url",
        "label",
        "attributes.occluded",
    ]


def test_print_annotation_attribute_list_as_csv_with_empty_list_outputs_header(tmp_path: Path):
    output_file = tmp_path / "out.csv"

    print_annotation_attribute_list_as_csv([], output_file)

    df = pandas.read_csv(output_file)
    assert list(df.columns) == [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "annotation_id",
        "annotation_editor_url",
        "label",
    ]
