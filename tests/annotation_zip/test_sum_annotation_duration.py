import argparse
import csv
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import annofabapi
import pandas
import pytest
from annofabapi.credentials import IdPass
from annofabapi.models import DefaultAnnotationType, InputDataType

from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator
from annofabcli.annotation_zip.sum_annotation_duration import (
    DurationOptions,
    SumAnnotationDuration,
    aggregate_annotation_durations,
    create_duration_dataframe,
    get_output_columns,
    make_output_rows,
    run_command,
)
from annofabcli.annotation_zip.sum_annotation_duration_by_attribute_value import add_parser as attribute_parser
from annofabcli.annotation_zip.sum_annotation_duration_by_label import add_parser as label_parser
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.common.utils import print_csv, print_json


@pytest.fixture
def sources():
    annotation = {
        "project_id": "p",
        "task_id": "t1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "v1",
        "input_data_name": "v1.mp4",
        "updated_datetime": None,
        "details": [
            {"label": "speech", "data": {"_type": "Range", "begin": 0, "end": 12000}, "attributes": {"speaker": "male", "flag": True, "tracking": "id1"}},
            {"label": "speech", "data": {"_type": "Range", "begin": 10000, "end": 18000}, "attributes": {"speaker": "female", "flag": False}},
            {"label": "music", "data": {"_type": "Range", "begin": 0, "end": 10000}, "attributes": {}},
            {"label": "speech", "data": {"_type": "Classification"}, "attributes": {}},
        ],
    }
    empty = {**deepcopy(annotation), "task_id": "t2", "details": []}
    second = {**deepcopy(annotation), "task_id": "t3", "input_data_id": "v2", "input_data_name": "v2.mp4", "details": []}
    inputs = [
        {"input_data_id": "v1", "system_metadata": {"input_duration": 20}},
        {"input_data_id": "v2", "system_metadata": {"input_duration": 10}},
        {"input_data_id": "unused", "system_metadata": {"input_duration": 999}},
    ]
    tasks = [
        {"task_id": "t1", "input_data_id_list": ["v1"], "metadata": {"customer": "A"}},
        {"task_id": "t2", "input_data_id_list": ["v1"], "metadata": {"customer": "B"}},
        {"task_id": "t3", "input_data_id_list": ["v2"], "metadata": {"customer": "A"}},
    ]
    return [annotation, empty, second], inputs, tasks


def output(
    sources: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]],
    options: DurationOptions,
    *,
    by_attribute: bool = False,
    translator: AnnotationNameTranslator | None = None,
) -> list[dict[str, Any]]:
    summaries = aggregate_annotation_durations(sources[0], sources[1], sources[2], options)
    return make_output_rows(
        summaries,
        options,
        by_attribute=by_attribute,
        label_columns=["speech", "music", "unused"],
        attribute_columns=[("speech", "speaker", value) for value in ["male", "female", "unknown"]] if by_attribute else [],
        translator=translator,
    )


def test_task_totals_overlaps_empty_and_shared_video(sources):
    rows = output(sources, DurationOptions())
    assert rows[0]["video_duration_second"] == 20
    assert rows[0]["annotation_duration_second"] == 30
    assert rows[0]["annotation_duration_second_by_label"] == {"speech": 20, "music": 10, "unused": 0}
    assert "input_data_count" not in rows[0]
    assert "frame_no" not in rows[0]
    assert rows[1]["annotation_duration_second"] == 0
    assert rows[1]["video_duration_second"] == 20
    assert "input_data_count" not in rows[1]
    assert rows[2]["video_duration_second"] == 10


def test_task_rows_include_input_data(sources):
    rows = output(sources, DurationOptions(with_task_metadata=True))
    assert len(rows) == 3
    assert rows[0]["video_duration_second"] == 20
    assert rows[0]["input_data_id"] == "v1"
    assert rows[0]["input_data_name"] == "v1.mp4"
    assert rows[0]["updated_datetime"] is None
    assert rows[2]["input_data_id"] == "v2"
    assert rows[0]["task_metadata"] == {"customer": "A"}
    assert "input_data_count" not in rows[0]


@pytest.mark.parametrize("groups", [["project_id"], ["task_phase", "task_status"]])
def test_summary_totals(sources, groups):
    rows = output(sources, DurationOptions(group_by=groups))
    assert len(rows) == 1
    assert rows[0]["video_duration_second"] == 50
    assert rows[0]["task_count"] == 3
    assert rows[0]["input_data_count"] == 3
    assert rows[0]["annotation_duration_second"] == 30


def test_metadata_grouping_and_type_distinction(sources):
    sources[2][0]["metadata"]["customer"] = True
    sources[2][1]["metadata"]["customer"] = 1
    sources[2][2]["metadata"]["customer"] = True
    rows = output(sources, DurationOptions(group_by=["task_metadata.customer"]))
    assert len(rows) == 2
    assert rows[0]["video_duration_second"] == 30
    assert rows[1]["video_duration_second"] == 20


def test_task_and_label_filters_keep_video_duration(sources):
    options = DurationOptions(task_ids=["t1"], label_names=["speech"])
    rows = output(sources, options)
    assert len(rows) == 1
    assert rows[0]["video_duration_second"] == 20
    assert rows[0]["annotation_duration_second"] == 20
    options.task_query = TaskQuery.from_dict({"status": "not_started"})
    assert output(sources, options) == []


def test_attribute_values_and_no_total(sources):
    options = DurationOptions(attribute_names=[("speech", "speaker"), ("speech", "flag")])
    rows = output(sources, options, by_attribute=True)
    assert rows[0]["annotation_duration_second_by_attribute_value"] == {"speech": {"speaker": {"male": 12, "female": 8, "unknown": 0}, "flag": {"true": 12, "false": 8}}}
    assert "annotation_duration_second" not in rows[0]
    assert rows[0]["video_duration_second"] == 20


@pytest.mark.parametrize("missing", [None, "absent"])
def test_unknown_duration_propagates_without_partial_sum(sources, missing):
    if missing is None:
        sources[1][1]["system_metadata"]["input_duration"] = None
    else:
        sources[1].pop(1)
    rows = output(sources, DurationOptions(group_by=["project_id"]))
    assert rows[0]["video_duration_second"] is None
    assert rows[0]["annotation_duration_second"] == 30


def test_zero_video_duration(sources):
    sources[1][0]["system_metadata"]["input_duration"] = 0
    assert output(sources, DurationOptions())[1]["video_duration_second"] == 0


@pytest.mark.parametrize("by_attribute", [False, True])
def test_json_and_csv_outputs(sources, tmp_path, by_attribute):
    options = DurationOptions(attribute_names=[("speech", "speaker")], with_task_metadata=True)
    rows = output(sources, options, by_attribute=by_attribute)
    json_path = tmp_path / "out.json"
    print_json(rows, is_pretty=True, output=json_path)
    assert json.loads(json_path.read_text()) == rows
    base = get_output_columns(options, sources[2])
    if not by_attribute:
        base.append("annotation_duration_second")
    columns = [("speech", "speaker", "male"), ("speech", "speaker", "female")] if by_attribute else ["speech", "music", "unused"]
    df = create_duration_dataframe(rows, base, columns, by_attribute=by_attribute)
    path = tmp_path / "out.csv"
    print_csv(df, path)
    with path.open(encoding="utf-8-sig", newline="") as file:
        csv_rows = list(csv.reader(file))
    assert len(csv_rows) == len(rows) + (3 if by_attribute else 1)
    if by_attribute:
        assert df[("speech", "speaker", "male")].tolist() == [12, 0, 0]
        assert df[("task_metadata.customer", "", "")].tolist() == ["A", "B", "A"]
    else:
        assert df["speech"].tolist() == [20, 0, 0]
    assert csv_rows[0][base.index("video_duration_second")] == "video_duration_second"


@pytest.mark.parametrize("by_attribute", [False, True])
def test_empty_csv_headers(sources, by_attribute):
    options = DurationOptions(group_by=["project_id"])
    columns = [("speech", "speaker", "male")] if by_attribute else ["speech"]
    df = create_duration_dataframe([], get_output_columns(options, sources[2]), columns, by_attribute=by_attribute)
    assert df.empty
    assert len(df.columns) == 5
    assert isinstance(df.columns, pandas.MultiIndex) == by_attribute


def test_japanese_name_collision_adds_durations(sources):
    translator = AnnotationNameTranslator({"labels": [], "additionals": []})
    translator._label_names = {"speech": "音", "music": "音"}
    rows = output(sources, DurationOptions(), translator=translator)
    assert rows[0]["annotation_duration_second_by_label"] == {"音": 30, "unused": 0}
    assert rows[0]["annotation_duration_second"] == 30


@pytest.mark.parametrize(
    ("by_attribute", "extra", "output_format"),
    [
        (False, [], "pretty_json"),
        (False, ["--label_name", "car"], "csv"),
        (True, [], "pretty_json"),
        (True, ["--attribute_name", "comment"], "pretty_json"),
        (True, ["--additional_attribute_name", "comment", "--group_by", "task_phase"], "csv"),
    ],
)
def test_command_with_api_boundary_mocks(sources, tmp_path, monkeypatch, by_attribute, extra, output_format):
    specs = json.loads(Path("tests/data/annotation_specs/annotation_specs.json").read_text(encoding="utf-8"))
    for label in specs["labels"]:
        label["annotation_type"] = DefaultAnnotationType.RANGE.value
    for annotation in sources[0]:
        for detail in annotation["details"]:
            detail["label"] = "car"
            detail["attributes"] = {"type": "large", "unclear": True, "comment": "hello"}
    annotation_zip = tmp_path / "annotations.zip"
    with zipfile.ZipFile(annotation_zip, "w") as archive:
        for annotation in sources[0]:
            archive.writestr(f"{annotation['task_id']}/{annotation['input_data_id']}.json", json.dumps(annotation))
    input_json = tmp_path / "inputs.json"
    task_json = tmp_path / "tasks.json"
    input_json.write_text(json.dumps(sources[1]))
    task_json.write_text(json.dumps(sources[2]))
    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test", "input_data_type": InputDataType.MOVIE.value}, None)))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": "owner"}, None)))
    monkeypatch.setattr(service.api, "get_annotation_specs", Mock(return_value=(specs, None)))
    monkeypatch.setattr(DownloadingFile, "download_input_data_json_to_dir", Mock(return_value=input_json))
    monkeypatch.setattr(DownloadingFile, "download_task_json_to_dir", Mock(return_value=task_json))
    parser = attribute_parser() if by_attribute else label_parser()
    output_path = tmp_path / "out"
    args = parser.parse_args(["--project_id", "p", "--annotation", str(annotation_zip), "--output", str(output_path), "--format", output_format, *extra])
    SumAnnotationDuration(service, AnnofabApiFacade(service), args).run(by_attribute=by_attribute)
    if output_format == "csv":
        frame = pandas.read_csv(output_path, header=[0, 1, 2] if by_attribute else 0)
        duration_column = next(column for column in frame.columns if (column[0] if by_attribute else column) == "video_duration_second")
        assert frame[duration_column].sum() == 50
        if by_attribute:
            assert frame[("car", "comment", "hello")].iloc[0] == 30
            assert frame[("car", "type", "large")].iloc[0] == 30
    else:
        rows = json.loads(output_path.read_text())
        assert rows[0]["video_duration_second"] == 20
        if by_attribute:
            attributes = rows[0]["annotation_duration_second_by_attribute_value"]["car"]
            if "--attribute_name" in extra:
                assert attributes == {"comment": {"hello": 30}}
            else:
                assert attributes["type"] == {"large": 30, "medium": 0, "small": 0}
                assert "comment" not in attributes
        else:
            assert rows[0]["annotation_duration_second"] == 30


@pytest.mark.parametrize("by_attribute", [False, True])
def test_input_data_group_is_rejected(by_attribute):
    args = argparse.Namespace(group_by=["input_data_id"])
    with pytest.raises(AnnofabCliException):
        run_command(args, by_attribute=by_attribute)


def test_multiple_input_data_task_is_rejected(sources):
    sources[2][0]["input_data_id_list"].append("v2")
    with pytest.raises(ValueError):
        output(sources, DurationOptions())
