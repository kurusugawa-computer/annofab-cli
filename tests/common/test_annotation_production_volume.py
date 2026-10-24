import json
import zipfile

import pytest

from annofabcli.common.annotation_production_volume import aggregate_annotation_production_volume
from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.dataframe.annotation_duration import AnnotationDuration


@pytest.fixture
def annotation_zip(tmp_path):
    path = tmp_path / "annotation.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for task_id, input_id, details in [
            ("t1", "i1", [{"label": "car", "data": {"_type": "Range", "begin": 0, "end": 60000}}, {"label": "car", "data": {"_type": "Range", "begin": 0, "end": 30000}}]),
            ("t1", "i2", [{"label": "person", "data": {"_type": "Range", "begin": 0, "end": 120000}}, {"label": "car", "data": {"_type": "Classification"}}]),
            ("t2", "i3", []),
        ]:
            archive.writestr(f"{task_id}/{input_id}.json", json.dumps({"task_id": task_id, "input_data_id": input_id, "details": details}))
    return path


@pytest.mark.parametrize(
    ("include", "exclude", "count", "duration"),
    [(None, None, 4, 3.5), (["car"], None, 3, 1.5), (None, ["car"], 1, 2.0), (["unknown"], None, 0, 0.0), (None, ["car", "person"], 0, 0.0)],
)
def test_aggregate_counts_and_duration_across_inputs(annotation_zip, include, exclude, count, duration):
    actual = aggregate_annotation_production_volume(annotation_zip, include_labels=include, exclude_labels=exclude)
    assert set(actual) == {"t1", "t2"}
    assert actual["t1"].annotation_count == count
    assert actual["t1"].annotation_duration_minute == duration
    assert actual["t2"].annotation_count == 0
    assert actual["t2"].annotation_duration_minute == 0


def test_unselected_json_and_external_files_are_not_loaded(annotation_zip):
    with zipfile.ZipFile(annotation_zip, "a") as archive:
        archive.writestr("unselected/input.json", "invalid json")
        archive.writestr("t1/i1/external-segment", b"\x00\x01")
    actual = aggregate_annotation_production_volume(annotation_zip, task_ids={"t1"})
    assert set(actual) == {"t1"}
    assert actual["t1"].annotation_count == 4


def test_existing_dataframe_wrappers_preserve_filtering_and_custom_counts(annotation_zip):
    counts = AnnotationCount.from_annotation_zip(annotation_zip, "p", include_labels=["car"], get_annotation_count_func=lambda annotation: len(annotation["details"]) * 2)
    durations = AnnotationDuration.from_annotation_zip(annotation_zip, "p", exclude_labels=["person"])
    assert counts.df.to_dict("records") == [{"project_id": "p", "task_id": "t1", "annotation_count": 6}, {"project_id": "p", "task_id": "t2", "annotation_count": 0}]
    assert durations.df.to_dict("records") == [{"project_id": "p", "task_id": "t1", "annotation_duration_minute": 1.5}, {"project_id": "p", "task_id": "t2", "annotation_duration_minute": 0.0}]


def test_empty_archive(tmp_path):
    path = tmp_path / "empty.zip"
    with zipfile.ZipFile(path, "w"):
        pass
    assert aggregate_annotation_production_volume(path) == {}
    assert AnnotationCount.from_annotation_zip(path, "p").is_empty()
    assert AnnotationDuration.from_annotation_zip(path, "p").is_empty()
