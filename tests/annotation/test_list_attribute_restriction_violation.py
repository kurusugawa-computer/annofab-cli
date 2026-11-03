from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from annofabcli.annotation.list_attribute_restriction_violation import ListAttributeRestrictionViolation, ListAttributeRestrictionViolationMain
from annofabcli.common.exceptions import AnnofabCliException


def name(value: str) -> dict:
    return {"messages": [{"lang": "en-US", "message": value}]}


@pytest.fixture
def specs() -> dict:
    return {
        "inspection_phrases": [],
        "labels": [
            {"label_id": "car", "label_name": name("car"), "additional_data_definitions": ["unclear", "comment", "link"]},
            {"label_id": "person", "label_name": name("person"), "additional_data_definitions": []},
        ],
        "additionals": [{"additional_data_definition_id": key, "name": name(key), "type": kind, "choices": []} for key, kind in [("unclear", "flag"), ("comment", "text"), ("link", "link")]],
        "restrictions": [
            {
                "additional_data_definition_id": "comment",
                "condition": {
                    "_type": "Imply",
                    "premise": {"additional_data_definition_id": "unclear", "condition": {"_type": "Equals", "value": "true"}},
                    "condition": {"_type": "NotEquals", "value": ""},
                },
            },
            {"additional_data_definition_id": "link", "condition": {"_type": "HasLabel", "labels": ["person"]}},
        ],
    }


def detail(annotation_id: str, label: str = "car", **attributes) -> dict:
    return {"annotation_id": annotation_id, "label": label, "attributes": attributes, "data": None}


def annotation(details: list[dict]) -> dict:
    return {"project_id": "prj1", "task_id": "task1", "input_data_id": "input1", "details": details}


def service_for(specs: dict, details: list[dict]) -> Mock:
    service = Mock()
    service.api.get_annotation_specs.return_value = specs, None
    service.api.get_project.return_value = {"input_data_type": "image"}, None
    service.api.get_task.return_value = {"input_data_id_list": ["input1"]}, None
    service.api.get_annotation.return_value = annotation(details), None
    return service


def test_imply_and_link_with_all_frame_annotations(specs: dict) -> None:
    service = service_for(
        specs,
        [
            detail("a1", unclear=True, comment="", link="a2"),
            detail("a2", "person"),
            detail("a3", unclear=False, link="a1"),
        ],
    )
    rows = ListAttributeRestrictionViolationMain(service, "prj1").validate_input_data("task1", "input1")
    assert [(row["annotation_id"], row["restriction_index"]) for row in rows] == [("a1", 0), ("a3", 1)]
    assert rows[0]["attribute_name_en"] == "comment"
    assert rows[0]["attribute_value"] == ""
    assert rows[0]["restriction"] == specs["restrictions"][0]
    assert "unclear" in rows[0]["restriction_text"]
    assert "a1" in rows[0]["annotation_editor_url"]


def test_failure_does_not_hide_remaining_results(specs: dict) -> None:
    service = service_for(specs, [])
    service.api.get_task.side_effect = [OSError(), ({"input_data_id_list": ["missing", "broken", "good", "empty"]}, None)]
    service.api.get_annotation.side_effect = [
        OSError(),
        (annotation([detail("a1", link="nonexistent")]), None),
        (annotation([detail("a2", unclear=True)]), None),
        (annotation([]), None),
    ]
    rows, failures = ListAttributeRestrictionViolationMain(service, "prj1").collect(["bad_task", "task1", "task1"])
    assert failures == 3
    assert [row["annotation_id"] for row in rows] == ["a2"]


def command(service: Mock, output: Path, output_format: str) -> ListAttributeRestrictionViolation:
    args = argparse.Namespace(project_id="prj1", task_id=["task1"], all_tasks=False, format=output_format, output=output, yes=False)
    facade = Mock()
    return ListAttributeRestrictionViolation(service, facade, args)


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_output_and_partial_failure(specs: dict, tmp_path: Path, output_format: str) -> None:
    service = service_for(specs, [])
    service.api.get_task.return_value = {"input_data_id_list": ["bad", "good"]}, None
    service.api.get_annotation.side_effect = [OSError(), (annotation([detail("a1", unclear=True)]), None)]
    output = tmp_path / "violations"
    with pytest.raises(AnnofabCliException):
        command(service, output, output_format).main()
    if output_format == "csv":
        with output.open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        assert json.loads(rows[0]["restriction"]) == specs["restrictions"][0]
    else:
        rows = json.loads(output.read_text())
        assert rows[0]["restriction"] == specs["restrictions"][0]
    assert len(rows) == 1
    assert rows[0]["annotation_id"] == "a1"


@pytest.mark.parametrize("output_format", ["csv", "json"])
def test_empty_output(specs: dict, tmp_path: Path, output_format: str) -> None:
    output = tmp_path / "empty"
    command(service_for(specs, []), output, output_format).main()
    if output_format == "csv":
        with output.open(encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames is not None
            assert "annotation_id" in reader.fieldnames
            assert list(reader) == []
    else:
        assert json.loads(output.read_text()) == []


def test_all_tasks_pagination_and_over_limit(specs: dict) -> None:
    service = service_for(specs, [])
    service.api.get_tasks.side_effect = [
        ({"list": [{"task_id": "t1"}], "page_no": 1, "total_page_no": 2, "over_limit": False}, None),
        ({"list": [{"task_id": "t2"}], "page_no": 2, "total_page_no": 2, "over_limit": False}, None),
        ({"list": [], "over_limit": True}, None),
    ]
    obj = ListAttributeRestrictionViolationMain(service, "prj1")
    assert obj.get_all_task_ids() == ["t1", "t2"]
    with pytest.raises(AnnofabCliException):
        obj.get_all_task_ids()


@pytest.mark.parametrize("read_only", [False, True])
def test_read_only_attributes_are_validated(specs: dict, *, read_only: bool) -> None:
    specs["additionals"][1]["read_only"] = read_only
    service = service_for(specs, [detail("a1", unclear=True)])
    rows = ListAttributeRestrictionViolationMain(service, "prj1").validate_input_data("task1", "input1")
    assert len(rows) == 1
    assert rows[0]["attribute_id"] == "comment"


def test_can_input_is_excluded(specs: dict) -> None:
    specs["restrictions"] = [{"additional_data_definition_id": "comment", "condition": {"_type": "CanInput", "enable": False}}]
    service = service_for(specs, [detail("a1", comment="saved")])
    assert ListAttributeRestrictionViolationMain(service, "prj1").validate_input_data("task1", "input1") == []
