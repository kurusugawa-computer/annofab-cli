from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from annofabapi.parser import lazy_parse_simple_annotation_dir

from annofabcli.annotation.get_annotation import GetAnnotationMain


def make_annotation(input_data_id: str, details: list[dict]) -> dict:
    return {
        "project_id": "prj1",
        "annotation_format_version": "1.2.0",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "working",
        "input_data_id": input_data_id,
        "input_data_name": f"{input_data_id}.jpg",
        "details": details,
    }


def test_get_preserves_simple_annotation_and_empty_input(tmp_path: Path) -> None:
    annotations = {
        "input1": make_annotation("input1", [{"label": "画像全体", "annotation_id": "a1", "data": None, "attributes": {"memo": "日本語"}}]),
        "input2": make_annotation("input2", []),
        "input3": make_annotation("input3", [{"label": "car", "annotation_id": "a3", "data": {"_type": "Unknown", "data": '{"kind":"CUBOID"}'}, "attributes": {}}]),
    }
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": list(annotations)}, None)
    service.api.get_annotation.side_effect = lambda _project_id, _task_id, input_data_id: (annotations[input_data_id], None)

    GetAnnotationMain(service, "prj1").get_annotation("task1", tmp_path)

    assert sorted(path.name for path in (tmp_path / "task1").iterdir()) == ["input1.json", "input2.json", "input3.json"]
    for input_data_id, annotation in annotations.items():
        assert json.loads((tmp_path / "task1" / f"{input_data_id}.json").read_text(encoding="utf-8")) == annotation
    service.api.get_editor_annotation.assert_not_called()
    assert len(list(lazy_parse_simple_annotation_dir(tmp_path))) == 3


@pytest.mark.parametrize(
    "data",
    [
        {"_type": "Segmentation", "data_uri": "a1"},
        {"_type": "SegmentationV2", "data_uri": "a1"},
        {"_type": "Unknown", "data": "./input1/a1"},
    ],
)
def test_get_downloads_outer_file_and_preserves_json(tmp_path: Path, data: dict) -> None:
    annotation = make_annotation("input1", [{"label": "road", "annotation_id": "a1", "data": data, "attributes": {}}])
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": ["input1"]}, None)
    service.api.get_annotation.return_value = (annotation, None)
    service.api.get_editor_annotation.return_value = (
        {"details": [{"annotation_id": "a1", "body": {"_type": "Outer", "url": "https://example.com/a1"}}]},
        None,
    )
    downloads = []

    def download(url, dest_path):
        downloads.append(url)
        dest_path.write_bytes(b"outer file")

    service.wrapper.download.side_effect = download

    GetAnnotationMain(service, "prj1").get_annotation("task1", tmp_path)

    assert downloads == ["https://example.com/a1"]
    assert (tmp_path / "task1" / "input1" / "a1").read_bytes() == b"outer file"
    assert json.loads((tmp_path / "task1" / "input1.json").read_text()) == annotation
    if data["_type"] != "Unknown":
        parser = next(lazy_parse_simple_annotation_dir(tmp_path))
        with parser.open_outer_file(data["data_uri"]) as outer_file:
            assert outer_file.read() == b"outer file"


def test_get_leaves_no_partial_task_on_download_failure(tmp_path: Path) -> None:
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": ["input1", "input2"]}, None)
    service.api.get_annotation.side_effect = [
        (make_annotation("input1", []), None),
        (make_annotation("input2", [{"annotation_id": "a1", "data": {"_type": "SegmentationV2", "data_uri": "a1"}}]), None),
    ]
    service.api.get_editor_annotation.return_value = ({"details": [{"annotation_id": "a1", "body": {"_type": "Outer", "url": "https://example.com/a1"}}]}, None)
    service.wrapper.download.side_effect = OSError()

    with pytest.raises(OSError):
        GetAnnotationMain(service, "prj1").get_annotation("task1", tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_get_refuses_existing_task_without_changing_files(tmp_path: Path) -> None:
    task_dir = tmp_path / "task1"
    task_dir.mkdir()
    existing_file = task_dir / "input1.json"
    existing_file.write_text("existing")
    service = Mock()

    with pytest.raises(FileExistsError):
        GetAnnotationMain(service, "prj1").get_annotation("task1", tmp_path)

    assert existing_file.read_text() == "existing"
    service.api.get_task.assert_not_called()


def test_get_fails_if_referenced_outer_annotation_disappears(tmp_path: Path) -> None:
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": ["input1"]}, None)
    service.api.get_annotation.return_value = (make_annotation("input1", [{"annotation_id": "a1", "data": {"_type": "SegmentationV2", "data_uri": "a1"}}]), None)
    service.api.get_editor_annotation.return_value = ({"details": []}, None)

    with pytest.raises(KeyError):
        GetAnnotationMain(service, "prj1").get_annotation("task1", tmp_path)

    assert list(tmp_path.iterdir()) == []
