from __future__ import annotations

import json
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import Mock

import pytest
from annofabapi.parser import lazy_parse_simple_annotation_dir

from annofabcli.annotation.get_annotation import GetAnnotationMain
from annofabcli.common.exceptions import AnnofabCliException


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

    GetAnnotationMain(service, "prj1").get_annotation_for_task("task1", tmp_path)

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

    GetAnnotationMain(service, "prj1").get_annotation_for_task("task1", tmp_path)

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
        GetAnnotationMain(service, "prj1").get_annotation_for_task("task1", tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_get_refuses_existing_task_without_changing_files(tmp_path: Path) -> None:
    task_dir = tmp_path / "task1"
    task_dir.mkdir()
    existing_file = task_dir / "input1.json"
    existing_file.write_text("existing")
    service = Mock()

    with pytest.raises(FileExistsError):
        GetAnnotationMain(service, "prj1").get_annotation_for_task("task1", tmp_path)

    assert existing_file.read_text() == "existing"
    service.api.get_task.assert_not_called()


def test_get_fails_if_referenced_outer_annotation_disappears(tmp_path: Path) -> None:
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": ["input1"]}, None)
    service.api.get_annotation.return_value = (make_annotation("input1", [{"annotation_id": "a1", "data": {"_type": "SegmentationV2", "data_uri": "a1"}}]), None)
    service.api.get_editor_annotation.return_value = ({"details": []}, None)

    with pytest.raises(KeyError):
        GetAnnotationMain(service, "prj1").get_annotation_for_task("task1", tmp_path)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("parallelism", [None, 2])
def test_get_multiple_tasks_with_duplicates(tmp_path: Path, parallelism: int | None) -> None:
    service = Mock()
    fetched_task_ids = []
    lock = Lock()

    def get_task(_project_id, task_id):
        with lock:
            fetched_task_ids.append(task_id)
        return {"input_data_id_list": ["input1", "input2"]}, None

    def get_annotation(_project_id, task_id, input_data_id):
        annotation = make_annotation(input_data_id, [])
        annotation["task_id"] = task_id
        return annotation, None

    service.api.get_task.side_effect = get_task
    service.api.get_annotation.side_effect = get_annotation

    GetAnnotationMain(service, "prj1").get_annotation(["task1", "task2", "task1"], tmp_path, parallelism=parallelism)

    assert sorted(fetched_task_ids) == ["task1", "task2"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["task1", "task2"]
    for task_id in ["task1", "task2"]:
        for input_data_id in ["input1", "input2"]:
            actual = json.loads((tmp_path / task_id / f"{input_data_id}.json").read_text())
            assert actual["task_id"] == task_id
            assert actual["input_data_id"] == input_data_id


def test_parallelism_runs_tasks_concurrently_and_inputs_sequentially(tmp_path: Path) -> None:
    service = Mock()
    barrier = Barrier(2)
    fetched_inputs: dict[str, list[str]] = {"task1": [], "task2": []}

    def get_task(_project_id, _task_id):
        # 2タスクが同時に開始しなければタイムアウトする。
        barrier.wait(timeout=10)
        return {"input_data_id_list": ["input1", "input2"]}, None

    def get_annotation(_project_id, task_id, input_data_id):
        fetched_inputs[task_id].append(input_data_id)
        return make_annotation(input_data_id, []), None

    service.api.get_task.side_effect = get_task
    service.api.get_annotation.side_effect = get_annotation

    GetAnnotationMain(service, "prj1").get_annotation(["task1", "task2"], tmp_path, parallelism=2)

    assert fetched_inputs == {"task1": ["input1", "input2"], "task2": ["input1", "input2"]}
    assert len(list(tmp_path.glob("*/*.json"))) == 4


@pytest.mark.parametrize("parallelism", [None, 2])
def test_task_failure_preserves_successful_tasks_and_cleans_partial_output(tmp_path: Path, parallelism: int | None, caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.get_task.return_value = ({"input_data_id_list": ["input1", "input2"]}, None)

    def get_annotation(_project_id, task_id, input_data_id):
        if task_id == "task2" and input_data_id == "input2":
            raise OSError
        annotation = make_annotation(input_data_id, [])
        annotation["task_id"] = task_id
        return annotation, None

    service.api.get_annotation.side_effect = get_annotation

    with pytest.raises(AnnofabCliException):
        GetAnnotationMain(service, "prj1").get_annotation(["task1", "task2", "task3"], tmp_path, parallelism=parallelism)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["task1", "task3"]
    assert len(list(tmp_path.glob("*/*.json"))) == 4
    assert any(record.exc_info is not None and "task2" in record.message for record in caplog.records)
