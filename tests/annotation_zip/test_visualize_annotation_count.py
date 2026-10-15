import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pytest
from annofabapi.credentials import IdPass
from bokeh.document import Document
from bokeh.models.annotations.labels import Title

from annofabcli.annotation_zip.count_annotation import CountTarget
from annofabcli.annotation_zip.visualize_annotation_count import VisualizeAnnotationCount
from annofabcli.annotation_zip.visualize_annotation_count_by_attribute_value import add_parser
from annofabcli.common.facade import AnnofabApiFacade


@pytest.mark.parametrize("group_by", ["task_id", "input_data_id"])
@pytest.mark.parametrize(
    ("options", "expected_labels", "expected_attribute"),
    [
        ([], {"car", "bike"}, None),
        (["--label_name", "car"], {"car"}, None),
        (["--label_name", "car", "bike"], {"car", "bike"}, None),
        (["--label_name", "missing"], set(), None),
        (["--label_name", "car", "missing"], {"car"}, None),
        (["--label_name", "file://labels.txt"], {"bike"}, None),
        (["--label_name", "car", "--attribute_name", "type"], {"car"}, "type"),
        (["--label_name", "car", "--additional_attribute_name", "comment"], {"car"}, None),
        (["--label_name", "car", "--use_japanese_name"], {"車"}, None),
    ],
)
def test_command_filters_histograms_by_label(tmp_path, monkeypatch, group_by, options, expected_labels, expected_attribute):
    specs = json.loads(Path("tests/data/annotation_specs/annotation_specs.json").read_text(encoding="utf-8"))
    car, bike = specs["labels"][:2]
    bike["additional_data_definitions"] = car["additional_data_definitions"].copy()
    for message in car["label_name"]["messages"]:
        if message["lang"] == "ja-JP":
            message["message"] = "車"
    service = annofabapi.Resource(IdPass("test", "test"))
    monkeypatch.setattr(service.api, "get_annotation_specs", Mock(side_effect=lambda *_args, **_kwargs: (deepcopy(specs), None)))
    monkeypatch.setattr(service.api, "get_project", Mock(return_value=({"title": "test"}, None)))
    monkeypatch.setattr(service.api, "get_my_member_in_project", Mock(return_value=({"member_role": "owner"}, None)))
    annotation_path = tmp_path / "annotations.zip"
    with zipfile.ZipFile(annotation_path, "w") as archive:
        for index in range(22):
            annotation = {
                "project_id": "project1",
                "task_id": f"task{index}",
                "task_phase": "acceptance",
                "task_phase_stage": 1,
                "task_status": "complete",
                "input_data_id": "input1",
                "input_data_name": "input1",
                "updated_datetime": "2026-01-01T00:00:00Z",
                "details": [{"label": label, "data": {"_type": "Classification"}, "attributes": {"type": "large", "unclear": True, "comment": "text"}} for label in ["car", "bike"]],
            }
            archive.writestr(f"task{index}/input1.json", json.dumps(annotation))
    labels_path = tmp_path / "labels.txt"
    labels_path.write_text("bike\n", encoding="utf-8")
    options = [f"file://{labels_path}" if value == "file://labels.txt" else value for value in options]
    output = tmp_path / "result.html"
    args = add_parser().parse_args(["--project_id", "project1", "--annotation", str(annotation_path), "--output", str(output), "--group_by", group_by, *options])

    VisualizeAnnotationCount(service, AnnofabApiFacade(service), args, count_target=CountTarget.ATTRIBUTE_VALUE).main()

    html = output.read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="[^"]+">(.*?)</script>', html, re.DOTALL)
    assert match is not None
    document = Document.from_json(next(iter(json.loads(match.group(1)).values())))
    all_titles = [str(title.text) for title in document.select({"type": Title}) if isinstance(title, Title)]
    titles = [title for title in all_titles if "," in title and not title.startswith("μ=")]
    assert {title.split(",")[0] for title in titles} == expected_labels
    if expected_attribute is not None:
        assert {title.split(",")[1] for title in titles} == {expected_attribute}
