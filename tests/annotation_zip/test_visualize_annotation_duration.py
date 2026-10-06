import argparse
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import numpy
import pytest
from annofabapi.credentials import IdPass
from annofabapi.models import DefaultAnnotationType, InputDataType
from bokeh.document import Document
from bokeh.models.annotations.labels import Title
from bokeh.models.renderers import GlyphRenderer
from bokeh.models.sources import ColumnDataSource

from annofabcli.annotation_zip import visualize_annotation_duration as duration_module
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator
from annofabcli.annotation_zip.visualize_annotation_duration import (
    TimeUnit,
    get_duration_plot_data,
    plot_annotation_duration_histogram_by_attribute,
    plot_annotation_duration_histogram_by_label,
)
from annofabcli.annotation_zip.visualize_annotation_duration_by_attribute_value import add_parser as attribute_parser
from annofabcli.annotation_zip.visualize_annotation_duration_by_label import add_parser as label_parser
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.statistics.list_annotation_duration import AnnotationSpecs, ListAnnotationDurationByInputData

output_dir = Path("./tests/out/annotation_zip/visualize_annotation_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


ANNOTATIONS = [
    {
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "input1",
        "input_data_name": "input1",
        "details": [
            {
                "label": "entire_video",
                "data": {"_type": "Classification"},
                "attributes": {"weather": "fine"},
            },
            {
                "label": "traffic_light",
                "data": {"begin": 3000, "end": 16000, "_type": "Range"},
                "attributes": {"color": "red"},
            },
            {
                "label": "traffic_light",
                "data": {"begin": 16000, "end": 24000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
            {
                "label": "traffic_light_for_pedestrian",
                "data": {"begin": 4000, "end": 9000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
        ],
        "updated_datetime": "2023-10-01T12:00:00Z",
    },
    {
        "project_id": "project1",
        "task_id": "task2",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "input1",
        "input_data_name": "input1",
        "details": [
            {
                "label": "entire_video",
                "data": {"_type": "Classification"},
                "attributes": {"weather": "fine"},
            },
            {
                "label": "traffic_light",
                "data": {"begin": 3000, "end": 160000, "_type": "Range"},
                "attributes": {"color": "red"},
            },
            {
                "label": "traffic_light",
                "data": {"begin": 16000, "end": 240000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
            {
                "label": "traffic_light_for_pedestrian",
                "data": {"begin": 4000, "end": 90000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
        ],
        "updated_datetime": "2023-10-02T12:00:00Z",
    },
]


def test__plot_annotation_duration_histogram_by_label__time_unitに秒を指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__time_unitに秒を指定する.html",
        time_unit=TimeUnit.SECOND,
    )


def test__plot_annotation_duration_histogram_by_label__time_unitに分を指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__time_unitに分を指定する.html",
        time_unit=TimeUnit.MINUTE,
    )


def test__plot_annotation_duration_histogram_by_label__bin_widthを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__bin_widthを指定する.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
    )


def test__plot_annotation_duration_histogram_by_label__arrange_bin_edgeを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__arrange_bin_edgeを指定する.html",
        time_unit=TimeUnit.SECOND,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_label__bin_widthとarrange_bin_edgeを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__bin_widthとarrange_bin_edgeを指定する.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_label__metadataを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__metadataを指定.html",
        time_unit=TimeUnit.SECOND,
        metadata={"project_id": "id", "project_title": "title1"},
    )


def test__plot_annotation_duration_histogram_by_attribute() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute.html",
        time_unit=TimeUnit.SECOND,
    )


def test__plot_annotation_duration_histogram_by_attribute__time_unitに分を指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "plot_annotation_duration_histogram_by_attribute__time_unitに分を指定.html",
        time_unit=TimeUnit.MINUTE,
    )


def test__plot_annotation_duration_histogram_by_attribute__arrange_bin_edgeを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__arrange_bin_edgeを指定.html",
        time_unit=TimeUnit.MINUTE,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
    )


def test__plot_annotation_duration_histogram_by_attribute__bin_widthとarrange_bin_edgeを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__bin_widthとarrange_bin_edgeを指定.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_attribute__metadataを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__metadataを指定.html",
        time_unit=TimeUnit.SECOND,
        metadata={"project_id": "id", "project_title": "title1"},
    )


@pytest.fixture
def command_inputs(tmp_path, monkeypatch):
    specs_json = json.loads(Path("tests/data/annotation_specs/annotation_specs.json").read_text(encoding="utf-8"))
    for label in specs_json["labels"]:
        label["annotation_type"] = DefaultAnnotationType.RANGE.value
        for message in label["label_name"]["messages"]:
            if message["lang"] == "ja-JP":
                message["message"] = f"日本語_{label['label_id']}"
    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test", "input_data_type": InputDataType.MOVIE.value}, None)))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": "owner"}, None)))
    monkeypatch.setattr(service.api, "get_annotation_specs", Mock(side_effect=lambda *_args, **_kwargs: (deepcopy(specs_json), None)))
    path = tmp_path / "annotations.zip"
    annotations = [
        {
            **deepcopy(ANNOTATIONS[0]),
            "task_id": f"task{i}",
            "details": [
                {"label": "car", "data": {"_type": "Range", "begin": 0, "end": 12000}, "attributes": {"type": "large", "unclear": True, "comment": f"comment{i}"}},
                {"label": "car", "data": {"_type": "Range", "begin": 10000, "end": 18000}, "attributes": {"type": "small", "unclear": False}},
            ]
            if i
            else [],
        }
        for i in range(22)
    ]
    with zipfile.ZipFile(path, "w") as archive:
        for annotation in annotations:
            archive.writestr(f"{annotation['task_id']}/input1.json", json.dumps(annotation))
    monkeypatch.setattr(DownloadingFile, "download_annotation_zip_to_dir", Mock(return_value=path))
    monkeypatch.setattr(duration_module, "build_annofabapi_resource_and_login", Mock(return_value=service))
    return service, path, specs_json


def load_html_document(path: Path) -> Document:
    html = path.read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="[^"]+">(.*?)</script>', html, re.DOTALL)
    assert match is not None
    payload = json.loads(match.group(1))
    return Document.from_json(next(iter(payload.values())))


@pytest.mark.parametrize("by_attribute", [False, True])
@pytest.mark.parametrize("local_annotation", [False, True])
def test_command_html_contains_task_histograms(command_inputs, tmp_path, by_attribute, local_annotation):
    _, path, _ = command_inputs
    output = tmp_path / "nested" / "duration.html"
    parser = attribute_parser() if by_attribute else label_parser()
    tokens = ["--project_id", "project1", "--output", str(output), "--time_unit", "minute", "--bin_width", "30", "--arrange_bin_edge"]
    if local_annotation:
        tokens += ["--annotation", str(path)]
    args = parser.parse_args(tokens)
    args.subcommand_func(args)
    document = load_html_document(output)
    renderers = [model for model in document.select({"type": GlyphRenderer}) if isinstance(model, GlyphRenderer)]
    assert renderers
    sources = [renderer.data_source for renderer in renderers if isinstance(renderer.data_source, ColumnDataSource)]
    assert len(sources) == len(renderers)
    assert all(sum(source.data["frequency"]) == 22 for source in sources)
    assert all(numpy.allclose(numpy.diff(source.data["left"]), 0.5) for source in sources)
    titles = {str(title.text) for title in document.select({"type": Title}) if isinstance(title, Title)}
    if by_attribute:
        assert "car,type,large" in titles
        assert not any("comment" in title for title in titles)
    else:
        assert "car" in titles


@pytest.mark.parametrize("option", ["--attribute_name", "--additional_attribute_name"])
def test_explicit_non_selective_attributes_are_not_limited_to_twenty_values(command_inputs, tmp_path, option):
    service, path, _ = command_inputs
    args = attribute_parser().parse_args(["--project_id", "project1", "--annotation", str(path), "--output", str(tmp_path / "out.html"), option, "comment"])
    specs = AnnotationSpecs(service, "project1", annotation_type=DefaultAnnotationType.RANGE.value)
    data = get_duration_plot_data(path, specs, args)
    comments = [key for key in data.attribute_keys if key[1] == "comment"]
    assert len(comments) == 21
    assert data.durations[1].annotation_duration_second_by_attribute[("car", "comment", "comment1")] == 12
    if option == "--attribute_name":
        assert all(key[1] == "comment" for key in data.attribute_keys)
    else:
        assert ("car", "type", "large") in data.attribute_keys
    args.subcommand_func(args)
    document = load_html_document(Path(args.output))
    assert len([title for title in document.select({"type": Title}) if isinstance(title, Title) and ",comment," in str(title.text)]) == 21


def test_filters_and_japanese_names(command_inputs, tmp_path):
    service, path, specs_json = command_inputs
    args = attribute_parser().parse_args(
        [
            "--project_id",
            "project1",
            "--annotation",
            str(path),
            "--output",
            str(tmp_path / "out.html"),
            "--label_name",
            "car",
            "--attribute_name",
            "type",
            "--task_id",
            "task1",
            "--task_query",
            '{"status":"complete"}',
            "--use_japanese_name",
        ]
    )
    specs = AnnotationSpecs(service, "project1", annotation_type=DefaultAnnotationType.RANGE.value)
    translator = AnnotationNameTranslator(specs_json)
    data = get_duration_plot_data(path, specs, args, translator)
    assert len(data.durations) == 1
    assert data.durations[0].annotation_duration_second_by_label == {translator.label_name("car"): 20}
    assert data.durations[0].annotation_duration_second_by_attribute == {
        translator.attribute_value_key(("car", "type", "large")): 12,
        translator.attribute_value_key(("car", "type", "small")): 8,
    }
    args.subcommand_func(args)
    titles = {str(title.text) for title in load_html_document(Path(args.output)).select({"type": Title}) if isinstance(title, Title)}
    assert ",".join(translator.attribute_value_key(("car", "type", "large"))) in titles


@pytest.mark.parametrize("by_attribute", [False, True])
@pytest.mark.parametrize("extra", [["--task_id", "missing"], ["--label_name", "missing"], ["--task_query", '{"status":"not_started"}']])
def test_empty_selection_outputs_html(command_inputs, tmp_path, by_attribute, extra):
    _, path, _ = command_inputs
    parser = attribute_parser() if by_attribute else label_parser()
    args = parser.parse_args(["--project_id", "project1", "--annotation", str(path), "--output", str(tmp_path / "empty.html"), "--arrange_bin_edge", *extra])
    args.subcommand_func(args)
    document = load_html_document(Path(args.output))
    assert not list(document.select({"type": GlyphRenderer}))


@pytest.mark.parametrize("width", [0, -1, float("nan"), float("inf")])
def test_invalid_bin_width_is_rejected(width):
    with pytest.raises(AnnofabCliException):
        duration_module.main(argparse.Namespace(bin_width=width))


def test_non_movie_project_is_rejected(command_inputs, tmp_path, monkeypatch):
    service, path, _ = command_inputs
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test", "input_data_type": "image"}, None)))
    args = label_parser().parse_args(["--project_id", "project1", "--annotation", str(path), "--output", str(tmp_path / "out.html")])
    with pytest.raises(AnnofabCliException):
        args.subcommand_func(args)


@pytest.mark.parametrize("by_attribute", [False, True])
def test_exclude_all_zero_histograms(command_inputs, tmp_path, by_attribute):
    _, path, _ = command_inputs
    parser = attribute_parser() if by_attribute else label_parser()
    args = parser.parse_args(
        [
            "--project_id",
            "project1",
            "--annotation",
            str(path),
            "--output",
            str(tmp_path / "zeros.html"),
            "--task_id",
            "task0",
            "--exclude_empty_value",
            "--arrange_bin_edge",
            "--bin_width",
            "0.5",
        ]
    )
    args.subcommand_func(args)
    assert not list(load_html_document(Path(args.output)).select({"type": GlyphRenderer}))


def test_multiple_input_data_task_is_rejected(command_inputs, tmp_path):
    service, path, _ = command_inputs
    with zipfile.ZipFile(path, "a") as archive:
        annotation = json.loads(archive.read("task1/input1.json"))
        annotation["input_data_id"] = "input2"
        archive.writestr("task1/input2.json", json.dumps(annotation))
    args = label_parser().parse_args(["--project_id", "project1", "--annotation", str(path), "--output", str(tmp_path / "out.html")])
    specs = AnnotationSpecs(service, "project1", annotation_type=DefaultAnnotationType.RANGE.value)
    with pytest.raises(AnnofabCliException):
        get_duration_plot_data(path, specs, args)
