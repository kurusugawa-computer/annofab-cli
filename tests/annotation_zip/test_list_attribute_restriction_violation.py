from __future__ import annotations

import argparse
import copy
import csv
import json
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

import annofabcli.annotation_zip.list_attribute_restriction_violation as command_module
from annofabcli.annotation_zip.list_attribute_restriction_violation import ListAttributeRestrictionViolation, ListAttributeRestrictionViolationMain
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


def write_annotation(directory: Path, task_id: str, input_data_id: str, details: list[dict]) -> None:
    path = directory / task_id / f"{input_data_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**annotation(details), "task_id": task_id, "input_data_id": input_data_id}), encoding="utf-8")


def test_imply_and_link_with_all_frame_annotations(specs: dict) -> None:
    source = annotation(
        [
            detail("a1", unclear=True, comment="", link="a2"),
            detail("a2", "person"),
            detail("a3", unclear=False, link="a1"),
        ]
    )
    rows = ListAttributeRestrictionViolationMain(specs).validate_input_data(source)
    assert [(row["annotation_id"], row["restriction_index"]) for row in rows] == [("a1", 0), ("a3", 1)]
    assert rows[0]["attribute_name"] == "comment"
    assert rows[0]["attribute_value"] == ""
    assert rows[0]["restriction"] == specs["restrictions"][0]
    assert "unclear" in rows[0]["restriction_text"]
    assert "a1" in rows[0]["annotation_editor_url"]


@pytest.mark.parametrize("source_type", ["zip", "directory"])
def test_failure_and_task_filter(specs: dict, tmp_path: Path, source_type: str) -> None:
    directory = tmp_path / "annotations"
    write_annotation(directory, "task1", "broken", [detail("a1", link="nonexistent")])
    write_annotation(directory, "task1", "good", [detail("a2", unclear=True)])
    write_annotation(directory, "task1", "empty", [])
    write_annotation(directory, "task2", "other", [detail("a3", unclear=True)])
    (directory / "task1" / "invalid.json").write_text("invalid JSON")
    # 絞り込み対象外の壊れたファイルは検証しない。
    (directory / "task2" / "invalid.json").write_text("invalid JSON")
    source = directory
    if source_type == "zip":
        source = tmp_path / "annotations.zip"
        with zipfile.ZipFile(source, "w") as archive:
            for path in directory.rglob("*.json"):
                archive.write(path, path.relative_to(directory))
    rows, failures = ListAttributeRestrictionViolationMain(specs).collect(source, ["task1"])
    assert failures == 2
    assert [row["annotation_id"] for row in rows] == ["a2"]


def command(output: Path, output_format: str) -> ListAttributeRestrictionViolation:
    args = argparse.Namespace(task_id=None, format=output_format, output=output, yes=False, use_japanese_name=False)
    return ListAttributeRestrictionViolation(args)


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_output_and_partial_failure(specs: dict, tmp_path: Path, output_format: str) -> None:
    source = tmp_path / "annotations"
    write_annotation(source, "task1", "bad", [detail("a2", link="nonexistent")])
    write_annotation(source, "task1", "good", [detail("a1", unclear=True)])
    output = tmp_path / "violations"
    with pytest.raises(AnnofabCliException):
        command(output, output_format).run(source, specs)
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
    source = tmp_path / "annotations"
    write_annotation(source, "task1", "empty", [])
    output = tmp_path / "empty"
    command(output, output_format).run(source, specs)
    if output_format == "csv":
        with output.open(encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames is not None
            assert "annotation_id" in reader.fieldnames
            assert list(reader) == []
    else:
        assert json.loads(output.read_text()) == []


@pytest.mark.parametrize("read_only", [False, True])
def test_read_only_attributes_are_validated(specs: dict, *, read_only: bool) -> None:
    specs["additionals"][1]["read_only"] = read_only
    rows = ListAttributeRestrictionViolationMain(specs).validate_input_data(annotation([detail("a1", unclear=True)]))
    assert len(rows) == 1
    assert rows[0]["attribute_id"] == "comment"


def test_can_input_is_excluded(specs: dict) -> None:
    specs["restrictions"] = [{"additional_data_definition_id": "comment", "condition": {"_type": "CanInput", "enable": False}}]
    assert ListAttributeRestrictionViolationMain(specs).validate_input_data(annotation([detail("a1", comment="saved")])) == []


@pytest.mark.parametrize("use_japanese_name", [False, True])
def test_local_files_need_no_authentication(specs: dict, tmp_path: Path, *, use_japanese_name: bool) -> None:
    source = tmp_path / "annotations"
    write_annotation(source, "task1", "input1", [detail("a1", unclear=True)])
    specs_path = tmp_path / "specs.json"
    specs_path.write_text(json.dumps(specs))
    output = tmp_path / "violations.json"
    args = argparse.Namespace(
        annotation=source,
        project_id=None,
        annotation_specs_json_file=specs_path,
        task_id=None,
        annotation_editor_type=None,
        output=output,
        format="json",
        yes=False,
        use_japanese_name=use_japanese_name,
    )
    command_module.main(args)
    assert json.loads(output.read_text())[0]["annotation_id"] == "a1"


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_japanese_names(specs: dict, tmp_path: Path, output_format: str) -> None:
    specs["labels"][0]["label_name"]["messages"].append({"lang": "ja-JP", "message": "車"})
    specs["additionals"][0]["name"]["messages"].append({"lang": "ja-JP", "message": "不明瞭"})
    specs["additionals"][1]["name"]["messages"].append({"lang": "ja-JP", "message": "状態"})
    specs["additionals"][1].update(
        type="select",
        choices=[
            {"choice_id": "ok", "name": name("ok")},
            {"choice_id": "bad", "name": {"messages": [{"lang": "en-US", "message": "bad"}, {"lang": "ja-JP", "message": "不良"}]}},
        ],
    )
    specs["restrictions"] = [{"additional_data_definition_id": "comment", "condition": {"_type": "Equals", "value": "ok"}}]
    original_specs = copy.deepcopy(specs)
    source = tmp_path / "annotations"
    write_annotation(source, "task1", "input1", [detail("a1", comment="bad")])
    output = tmp_path / "violations"
    cli = command(output, output_format)
    cli.args.use_japanese_name = True
    cli.run(source, specs)
    if output_format == "csv":
        with output.open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["restriction"] = json.loads(rows[0]["restriction"])
    else:
        rows = json.loads(output.read_text())
    assert len(rows) == 1
    assert rows[0]["label_name"] == "車"
    assert rows[0]["attribute_name"] == "状態"
    assert rows[0]["attribute_value"] == "不良"
    assert "状態" in rows[0]["restriction_text"]
    assert "ok" in rows[0]["restriction_text"]
    assert rows[0]["restriction"] == specs["restrictions"][0]
    assert specs == original_specs


def test_japanese_names_preserve_free_text_and_fallback(specs: dict) -> None:
    specs["additionals"][0]["name"]["messages"].append({"lang": "ja-JP", "message": "不明瞭"})
    specs["restrictions"] = [{"additional_data_definition_id": "comment", "condition": {"_type": "Equals", "value": "expected"}}]
    rows = ListAttributeRestrictionViolationMain(specs, use_japanese_name=True).validate_input_data(annotation([detail("a1", comment="free text")]))
    assert rows[0]["label_name"] == "car"
    assert rows[0]["attribute_name"] == "comment"
    assert rows[0]["attribute_value"] == "free text"
    assert "comment" in rows[0]["restriction_text"]


def test_project_download_and_task_filter(specs: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Mock()
    service.api.get_project.return_value = {"title": "example", "input_data_type": "image"}, None
    service.api.get_my_member_in_project.return_value = {"member_role": "owner"}, None
    service.api.get_annotation_specs.return_value = specs, None

    def download(_project_id, dest_path):
        with zipfile.ZipFile(dest_path, "w") as archive:
            for task_id in ["task1", "task2"]:
                data = {**annotation([detail("a1", unclear=True)]), "task_id": task_id}
                archive.writestr(f"{task_id}/input1.json", json.dumps(data))

    service.wrapper.download_annotation_zip.side_effect = download
    monkeypatch.setattr(command_module, "build_annofabapi_resource_and_login", Mock(return_value=service))
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("task2\n")
    output = tmp_path / "violations.json"
    args = argparse.Namespace(
        annotation=None,
        project_id="prj1",
        annotation_specs_json_file=None,
        task_id=[f"file://{task_file}"],
        annotation_editor_type=None,
        output=output,
        format="json",
        yes=False,
        temp_dir=tmp_path / "download",
        latest=False,
        use_japanese_name=False,
    )
    command_module.main(args)
    rows = json.loads(output.read_text())
    assert len(rows) == 1
    assert rows[0]["task_id"] == "task2"
    assert len(list(args.temp_dir.glob("*.zip"))) == 1


@pytest.mark.parametrize(("condition_type", "actual_value"), [("Equals", True), ("NotEquals", False)])
def test_false_flag_comparison_preserves_all_violations(specs: dict, condition_type: str, *, actual_value: bool) -> None:
    specs["restrictions"] = [
        {"additional_data_definition_id": "unclear", "condition": {"_type": condition_type, "value": "false"}},
        {"additional_data_definition_id": "comment", "condition": {"_type": "NotEquals", "value": ""}},
    ]
    rows = ListAttributeRestrictionViolationMain(specs).validate_input_data(annotation([detail("a1", unclear=actual_value)]))
    assert [row["attribute_id"] for row in rows] == ["unclear", "comment"]
    assert rows[0]["attribute_value"] is actual_value
    assert rows[0]["restriction"] == specs["restrictions"][0]
    assert rows[0]["restriction_text"]
