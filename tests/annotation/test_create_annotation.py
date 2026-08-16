import json
from pathlib import Path
from typing import Any, cast

import annofabapi

from annofabcli.annotation.create_annotation import CreateAnnotationItem, create_request_body
from annofabcli.annotation.import_annotation import AnnotationConverter

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text(encoding="utf-8"))

project: dict[str, Any] = {
    "project_id": "project_id",
    "input_data_type": "image",
    "configuration": {"plugin_id": None},
}


def test_create_request_body__既存アノテーションを変更せず新規アノテーションを追加する():
    editor_annotation = {
        "project_id": "project_id",
        "task_id": "task_id",
        "input_data_id": "input_data_id",
        "updated_datetime": "2026-08-16T00:00:00+09:00",
        "details": [
            {
                "annotation_id": "existing",
                "label_id": "label_id",
                "additional_data_list": [],
                "editor_props": {"can_delete": True},
                "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
            }
        ],
    }
    converter = AnnotationConverter(project, annotation_specs, service=cast(annofabapi.Resource, None), default_editor_props={"can_delete": False})
    items = [
        CreateAnnotationItem(
            task_id="task_id",
            input_data_id="input_data_id",
            annotation_id="existing",
            label="car",
            data={"_type": "BoundingBox", "left_top": {"x": 100, "y": 200}, "right_bottom": {"x": 300, "y": 400}},
        ),
        CreateAnnotationItem(
            task_id="task_id",
            input_data_id="input_data_id",
            annotation_id="new",
            label="car",
            data={"_type": "BoundingBox", "left_top": {"x": 100, "y": 200}, "right_bottom": {"x": 300, "y": 400}},
            editor_props={"can_delete": True},
        ),
    ]

    actual = create_request_body(editor_annotation, items, converter=converter)

    assert actual.count.success == 1
    assert actual.count.failed == 1
    assert actual.request_body["details"][0] == {
        "annotation_id": "existing",
        "label_id": "label_id",
        "additional_data_list": [],
        "editor_props": {"can_delete": True},
        "body": None,
        "_type": "Update",
    }
    assert actual.request_body["details"][1]["_type"] == "Create"
    assert actual.request_body["details"][1]["annotation_id"] == "new"
    assert actual.request_body["details"][1]["editor_props"] == {"can_delete": True}
