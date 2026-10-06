import json
import logging
import zipfile
from pathlib import Path
from unittest.mock import Mock

import annofabapi
from annofabapi.credentials import IdPass
from annofabapi.models import DefaultAnnotationType, InputDataType

from annofabcli.statistics import visualize_annotation_duration


def test_deprecated_command_warns_and_preserves_both_outputs(tmp_path, monkeypatch, caplog):
    specs = json.loads(Path("tests/data/annotation_specs/annotation_specs.json").read_text(encoding="utf-8"))
    for label in specs["labels"]:
        label["annotation_type"] = DefaultAnnotationType.RANGE.value
    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test", "input_data_type": InputDataType.MOVIE.value}, None)))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": "owner"}, None)))
    monkeypatch.setattr(service.api, "get_annotation_specs", Mock(return_value=(specs, None)))
    monkeypatch.setattr(visualize_annotation_duration, "build_annofabapi_resource_and_login", Mock(return_value=service))
    annotation = {
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "input1",
        "input_data_name": "input1",
        "updated_datetime": None,
        "details": [{"label": "car", "data": {"_type": "Range", "begin": 0, "end": 10000}, "attributes": {"type": "large"}}],
    }
    path = tmp_path / "annotation.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("task1/input1.json", json.dumps(annotation))
    output_dir = tmp_path / "out"
    args = visualize_annotation_duration.add_parser().parse_args(["--project_id", "project1", "--annotation", str(path), "--output_dir", str(output_dir)])
    caplog.set_level(logging.WARNING)
    args.subcommand_func(args)
    assert {file.name for file in output_dir.iterdir()} == {"annotation_duration_by_label.html", "annotation_duration_by_attribute.html"}
    assert "[DEPRECATED]" in caplog.text
    assert "2027-01-01以降の最初のリリース" in caplog.text
    assert "annotation_zip visualize_annotation_duration_by_label" in caplog.text
    assert "annotation_zip visualize_annotation_duration_by_attribute_value" in caplog.text
