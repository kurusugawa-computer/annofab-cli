from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import annofabapi
import pytest

from annofabcli.annotation.normalize_attribute_type import NormalizeAttributeTypeMain, create_normalized_request, normalize_attribute_value


@pytest.mark.parametrize(
    ("value", "target_type", "expected"),
    [
        ({"_type": "Text", "value": "4"}, "comment", {"_type": "Comment", "value": "4"}),
        *[({"_type": "Comment", "value": text}, "text", {"_type": "Text", "value": text}) for text in ["a\nb", "a\rb", "a\r\nb"]],
        ({"_type": "Comment", "value": "hello"}, "text", {"_type": "Text", "value": "hello"}),
        ({"_type": "Choice", "choice_id": "c1"}, "select", {"_type": "Select", "choice_id": "c1"}),
        ({"_type": "Select", "choice_id": "c1"}, "choice", {"_type": "Choice", "choice_id": "c1"}),
        ({"_type": "Integer", "value": -4}, "text", {"_type": "Text", "value": "-4"}),
        *[
            ({"_type": source_type, "value": text}, "integer", {"_type": "Integer", "value": number})
            for source_type in ["Text", "Comment"]
            for text, number in [("4", 4), ("04", 4), ("+4", 4), (" 4 ", 4), ("-0", 0), ("-4", -4), ("1_000", 1000), ("4\n", 4)]
        ],
        ({"_type": "Text", "value": ""}, "comment", {"_type": "Comment", "value": ""}),
        ({"_type": "Text", "value": "abc"}, "text", {"_type": "Text", "value": "abc"}),
        ({"_type": "Flag", "value": False}, "flag", {"_type": "Flag", "value": False}),
    ],
)
def test_normalize_attribute_value(value: dict, target_type: str, expected: dict) -> None:
    original = copy.deepcopy(value)
    attribute = {"type": target_type, "choices": [{"choice_id": "c1"}]}
    assert normalize_attribute_value(value, attribute) == expected
    assert value == original


@pytest.mark.parametrize(
    ("value", "target_type"),
    [
        *[({"_type": source_type, "value": text}, "integer") for source_type in ["Text", "Comment"] for text in ["", "abc", "4.0", "4\n5", None]],
        ({"_type": "Integer", "value": True}, "text"),
        ({"_type": "Integer", "value": 4.5}, "text"),
        ({"_type": "Text", "value": "4"}, "select"),
        *[({"_type": "Text", "value": text}, "comment") for text in ["a\nb", "a\rb", "a\r\nb"]],
        ({"_type": "Choice", "choice_id": "missing"}, "select"),
    ],
)
def test_unconvertible_value(value: dict, target_type: str) -> None:
    with pytest.raises(ValueError):
        normalize_attribute_value(value, {"type": target_type, "choices": [{"choice_id": "c1"}]})


def specs() -> dict:
    return {
        "labels": [{"label_id": "label1", "additional_data_definitions": ["a1", "a2", "a3", "a4"]}],
        "additionals": [
            {"additional_data_definition_id": "a1", "type": "comment"},
            {"additional_data_definition_id": "a2", "type": "integer"},
            {"additional_data_definition_id": "a3", "type": "flag"},
            {"additional_data_definition_id": "a4", "type": "text"},
        ],
    }


def annotation() -> dict:
    return {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-10-27T00:00:00Z",
        "format_version": "2.0.0",
        "details": [
            {
                "annotation_id": "anno1",
                "label_id": "label1",
                "body": {"_type": "Inner", "data": {"_type": "Classification"}},
                "editor_props": {"visible": True},
                "additional_data_list": [
                    {"definition_id": "a1", "value": {"_type": "Text", "value": "4"}},
                    {"definition_id": "a2", "value": {"_type": "Text", "value": "invalid"}},
                    {"definition_id": "a3", "value": {"_type": "Flag", "value": False}},
                    {"definition_id": "a4", "value": None},
                    {"definition_id": "deleted", "value": {"_type": "Text", "value": "keep"}},
                ],
            }
        ],
    }


@pytest.mark.parametrize("source_type", ["Text", "Comment"])
def test_request_preserves_unconvertible_and_unrelated_data_and_is_idempotent(source_type: str) -> None:
    source = annotation()
    source["details"][0]["additional_data_list"][1]["value"]["_type"] = source_type
    original = copy.deepcopy(source)
    request, result = create_normalized_request(source, specs())
    assert (result.changed, result.skipped) == (1, 2)
    assert source == original
    assert request == [
        {
            "_type": "PutV2",
            "data": {
                "project_id": "project1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": source["updated_datetime"],
                "annotation_id": "anno1",
                "label_id": "label1",
                "additional_data_list": [{"definition_id": "a1", "value": {"_type": "Comment", "value": "4"}}],
            },
        }
    ]
    source["details"][0]["additional_data_list"][0] = request[0]["data"]["additional_data_list"][0]
    repeated_request, repeated = create_normalized_request(source, specs())
    assert repeated.changed == 0
    assert repeated_request == []


def test_attribute_filter() -> None:
    request, result = create_normalized_request(annotation(), specs(), attribute_ids={"a3"})
    assert result.changed == result.skipped == 0
    assert request == []


@pytest.mark.parametrize("label_id", ["missing_label", "label_without_attributes"])
def test_attributes_outside_current_label_are_preserved(label_id: str) -> None:
    source = annotation()
    source["details"][0]["label_id"] = label_id
    definitions = specs()
    definitions["labels"].append({"label_id": "label_without_attributes", "additional_data_definitions": []})
    request, result = create_normalized_request(source, definitions)
    assert result.changed == 0
    assert result.skipped == 4
    assert request == []


def service_with_annotation() -> Mock:
    service = Mock()
    service.wrapper.get_task_or_none.return_value = {"status": "not_started", "input_data_id_list": ["input1"]}
    service.api.get_editor_annotations_in_bulk.return_value = ({"success": [annotation()], "failure": []}, None)
    return service


def test_update_and_backup(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="annofabcli.annotation.normalize_attribute_type")
    service = service_with_annotation()
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), backup_dir=tmp_path, all_yes=True).normalize_for_task((0, "task1"))
    assert (result.changed, result.skipped, result.failed_input_data, result.failed_tasks) == (1, 2, 0, 0)
    service.api.batch_update_annotations.assert_called_once()
    request = service.api.batch_update_annotations.call_args.kwargs["request_body"]
    assert request[0]["data"]["updated_datetime"] == annotation()["updated_datetime"]
    assert "body" not in request[0]["data"]
    assert (tmp_path / "task1" / "input1.json").is_file()
    assert "属性値の型を1件変更しました。変換できず保持した属性値: 2件、処理に失敗した入力データ: 0件、処理に失敗したタスク: 0件。" in caplog.text


def test_dry_run_does_not_write_or_backup(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="annofabcli.annotation.normalize_attribute_type")
    service = service_with_annotation()
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), backup_dir=tmp_path, dry_run=True).normalize_for_task((0, "task1"))
    assert result.changed == 1
    service.api.batch_update_annotations.assert_not_called()
    assert list(tmp_path.iterdir()) == []
    assert "属性値の型を1件変更する予定です。" in caplog.text
    assert "変更しました" not in caplog.text


@pytest.mark.parametrize("status", ["working", "complete", "on_hold"])
def test_skip_task_status(status: str) -> None:
    service = service_with_annotation()
    service.wrapper.get_task_or_none.return_value["status"] = status
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), all_yes=True).normalize_for_task((0, "task1"))
    assert result.changed == result.failed_input_data == result.failed_tasks == 0
    service.api.batch_update_annotations.assert_not_called()


@pytest.mark.parametrize("status", ["complete", "on_hold"])
def test_explicitly_include_task_status(status: str) -> None:
    service = service_with_annotation()
    service.wrapper.get_task_or_none.return_value["status"] = status
    result = NormalizeAttributeTypeMain(
        cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), include_complete_task=True, include_on_hold_task=True, all_yes=True
    ).normalize_for_task((0, "task1"))
    assert result.changed == 1
    service.api.batch_update_annotations.assert_called_once()


def test_no_updates_when_already_normalized() -> None:
    service = service_with_annotation()
    normalized = annotation()
    normalized["details"][0]["additional_data_list"] = [{"definition_id": "a1", "value": {"_type": "Comment", "value": "4"}}]
    service.api.get_editor_annotations_in_bulk.return_value = ({"success": [normalized], "failure": []}, None)
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), all_yes=True).normalize_for_task((0, "task1"))
    assert result.changed == 0
    service.api.batch_update_annotations.assert_not_called()


def test_failure_does_not_stop_other_inputs() -> None:
    service = service_with_annotation()
    service.wrapper.get_task_or_none.return_value["input_data_id_list"] = ["input1", "input2"]
    second = annotation()
    second["input_data_id"] = "input2"
    service.api.get_editor_annotations_in_bulk.return_value = ({"success": [annotation(), second], "failure": []}, None)
    service.api.batch_update_annotations.side_effect = [RuntimeError("failure"), None]
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), all_yes=True).normalize_for_task((0, "task1"))
    assert result.changed == result.failed_input_data == 1
    assert result.failed_tasks == 0
    assert service.api.batch_update_annotations.call_count == 2


def test_task_failure_is_counted_separately() -> None:
    service = service_with_annotation()
    service.wrapper.get_task_or_none.side_effect = RuntimeError("failure")
    result = NormalizeAttributeTypeMain(cast(annofabapi.Resource, service), project_id="project1", annotation_specs=specs(), all_yes=True).normalize_for_task((0, "task1"))
    assert result.changed == result.failed_input_data == 0
    assert result.failed_tasks == 1
    service.api.batch_update_annotations.assert_not_called()
