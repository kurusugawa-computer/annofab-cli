import argparse
import json
import logging
from contextlib import nullcontext
from pathlib import Path
from threading import Barrier
from typing import Any
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli.annotation.create_annotation
from annofabcli.annotation.create_annotation import (
    CreateAnnotation,
    CreateAnnotationCount,
    CreateAnnotationItem,
    CreateAnnotationMain,
    create_request_body,
    filter_annotation_items_by_task_ids,
    get_annotation_items_from_csv,
)
from annofabcli.annotation.create_annotation_converter import CreateAnnotationConverter
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.common.exceptions import AnnofabCliException

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text(encoding="utf-8"))

project: dict[str, Any] = {
    "project_id": "project_id",
    "input_data_type": "image",
    "configuration": {"plugin_id": None},
}


@pytest.mark.parametrize("annotation_id", [None, "fcb847a5-5607-4467-a72b-fc11fb5cfbab", "wrong_id", ""])
@pytest.mark.parametrize("has_existing_annotation", [False, True])
@pytest.mark.parametrize("input_data_type", ["image", "movie"])
def test_create_request_body__全体アノテーションはlabel_idで作成または既存判定する(annotation_id, has_existing_annotation, input_data_type, caplog):
    label_id = "fcb847a5-5607-4467-a72b-fc11fb5cfbab"
    existing_detail = {"annotation_id": label_id, "label_id": label_id, "additional_data_list": [], "body": {"_type": "Inner", "data": {"_type": "Classification"}}}
    editor_annotation = {
        "project_id": "project_id",
        "task_id": "t1",
        "input_data_id": "i1",
        "updated_datetime": "2026-10-12T00:00:00+09:00",
        "details": [existing_detail] if has_existing_annotation else [],
    }
    converter = CreateAnnotationConverter({**project, "input_data_type": input_data_type}, annotation_specs, default_editor_props={})
    items = [CreateAnnotationItem(task_id="t1", input_data_id="i1", annotation_id=annotation_id, label="whole", data={"_type": "Classification"})]

    actual = create_request_body(editor_annotation, items, converter=converter)

    assert actual.count == CreateAnnotationCount(success=0 if has_existing_annotation else 1, failed=1 if has_existing_annotation else 0)
    assert len(actual.request_body["details"]) == 1
    assert actual.request_body["details"][0]["annotation_id"] == label_id
    assert actual.request_body["details"][0]["_type"] == ("Update" if has_existing_annotation else "Create")
    if has_existing_annotation:
        assert actual.request_body["details"][0]["body"] is None
    if annotation_id is not None and annotation_id != label_id:
        assert f"指定されたannotation_id='{annotation_id}'は無視します。" in caplog.text


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
    converter = CreateAnnotationConverter(project, annotation_specs, default_editor_props={"can_delete": False})
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


@pytest.mark.parametrize(
    ("task_status", "option_name"),
    [
        (TaskStatus.COMPLETE, "--include_complete_task"),
        (TaskStatus.BREAK, "--include_break_task"),
        (TaskStatus.ON_HOLD, "--include_on_hold_task"),
    ],
)
def test_create_for_task__対象外状態のタスクを処理するオプションをログに出力する(task_status: TaskStatus, option_name: str, caplog: pytest.LogCaptureFixture) -> None:
    service = Mock()
    service.api.account_id = "my_account_id"
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task_id",
        "status": task_status.value,
        "account_id": "my_account_id",
        "updated_datetime": "2026-08-16T00:00:00+09:00",
    }
    obj = CreateAnnotationMain(
        service,
        project_id="project_id",
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        all_yes=True,
        converter=Mock(),
        backup_dir=None,
    )

    with caplog.at_level(logging.INFO):
        actual = obj.create_for_task("task_id", {"input_data_id": [Mock()]})

    assert actual == CreateAnnotationCount(success=0, failed=1)
    assert option_name in caplog.text


def test_get_annotation_items_from_csv__必須カラムが不足している場合は例外を送出する(tmp_path):
    csv_path = tmp_path / "annotations.csv"
    csv_path.write_text("task_id,input_data_id,label\nt1,i1,car\n", encoding="utf-8")

    with pytest.raises(ValueError):
        get_annotation_items_from_csv(str(csv_path))


def test_get_annotation_items_from_csv__JSON形式が不正な場合は例外を送出する(tmp_path):
    csv_path = tmp_path / "annotations.csv"
    csv_path.write_text("task_id,input_data_id,label,data\nt1,i1,car,invalid-json\n", encoding="utf-8")

    with pytest.raises(ValueError):
        get_annotation_items_from_csv(str(csv_path))


def test_filter_annotation_items_by_task_ids__指定したtask_idのアノテーションだけを返す() -> None:
    items = [
        CreateAnnotationItem(task_id="task1", input_data_id="input1", label="car", data={"_type": "BoundingBox"}),
        CreateAnnotationItem(task_id="task2", input_data_id="input2", label="car", data={"_type": "BoundingBox"}),
        CreateAnnotationItem(task_id="task1", input_data_id="input3", label="person", data={"_type": "BoundingBox"}),
    ]

    actual_items, actual_not_existing_task_ids = filter_annotation_items_by_task_ids(items, ["task1", "task3"])

    assert [item.task_id for item in actual_items] == ["task1", "task1"]
    assert [item.input_data_id for item in actual_items] == ["input1", "input3"]
    assert actual_not_existing_task_ids == {"task3"}


def test_main__task_idで絞り込みし存在しないtask_idを警告する(tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    task_id_path = tmp_path / "task_id.txt"
    task_id_path.write_text("task1\ntask3\n", encoding="utf-8")
    args = argparse.Namespace(
        project_id="project_id",
        json=json.dumps(
            [
                {"task_id": "task1", "input_data_id": "input1", "label": "car", "data": {"_type": "BoundingBox"}},
                {"task_id": "task2", "input_data_id": "input2", "label": "car", "data": {"_type": "BoundingBox"}},
            ]
        ),
        csv=None,
        task_id=[f"file://{task_id_path}"],
        backup=str(tmp_path / "backup"),
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        change_operator_to_me=False,
        editor_props=None,
        yes=True,
        parallelism=None,
    )
    service = Mock()
    service.api.get_annotation_specs.return_value = (annotation_specs, None)
    service.api.get_project.return_value = (project, None)
    facade = Mock()
    main_instance = Mock()
    monkeypatch.setattr(annofabcli.annotation.create_annotation, "CreateAnnotationMain", Mock(return_value=main_instance))

    with caplog.at_level(logging.WARNING):
        annofabcli.annotation.create_annotation.CreateAnnotation(service, facade, args).main()

    actual_items = main_instance.create.call_args.args[0]
    assert [item.task_id for item in actual_items] == ["task1"]
    assert [item.input_data_id for item in actual_items] == ["input1"]
    assert "task3" in caplog.text


@pytest.mark.parametrize("failure", ["none", "get_task", "restore"])
@pytest.mark.parametrize("parallelism", [None, 2])
@pytest.mark.parametrize("role", ["owner", "accepter"])
def test_task_parallelism_preserves_backup_order_and_status_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture, parallelism: int | None, role: str, failure: str) -> None:
    service = Mock()
    barrier = Barrier(2)
    updates: list[tuple[str, str]] = []
    events: list[tuple[str, str]] = []

    def get_task(_project_id, task_id):
        if failure == "get_task" and task_id == "task1":
            raise RuntimeError("task API failure")
        if failure == "none" and parallelism is not None and task_id in {"task1", "task2"}:
            barrier.wait(timeout=10)
        return {"task_id": task_id, "status": "complete" if task_id == "complete" else "not_started", "account_id": "old_operator", "updated_datetime": "2026-01-01T00:00:00Z"}

    def get_annotations(project_id, task_id, *, query_params):
        return {
            "success": [
                {"project_id": project_id, "task_id": task_id, "input_data_id": input_id, "updated_datetime": "2026-01-01T00:00:00Z", "format_version": "2.0.0", "details": []}
                for input_id in query_params["input_data_id"].split(",")
            ],
            "failure": [],
        }, None

    def update(_project_id, *_args, request_body, **_kwargs):
        annotation = request_body
        task_id, input_id = annotation["task_id"], annotation["input_data_id"]
        backup = json.loads((tmp_path / task_id / f"{input_id}.json").read_text())
        assert backup["input_data_id"] == input_id
        assert request_body["details"][0]["_type"] == "Create"
        updates.append((task_id, input_id))
        events.append((task_id, input_id))
        return {}, None

    def change_operator(_project_id, task_id, *, operator_account_id, last_updated_datetime):
        events.append((task_id, operator_account_id))
        if failure == "restore" and task_id == "task1" and operator_account_id == "old_operator":
            raise RuntimeError("operator API failure")
        return {"updated_datetime": last_updated_datetime}

    service.api.account_id = "current_operator"
    service.wrapper.change_task_operator.side_effect = change_operator
    service.wrapper.get_task_or_none.side_effect = get_task
    service.api.get_editor_annotations_in_bulk.side_effect = get_annotations
    service.api.put_annotation.side_effect = update
    service.api.get_my_member_in_project.return_value = ({"member_role": role}, None)
    main_obj = CreateAnnotationMain(
        service,
        project_id="project1",
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        all_yes=True,
        backup_dir=tmp_path,
        converter=CreateAnnotationConverter(project, annotation_specs, default_editor_props={}),
    )
    items = [
        CreateAnnotationItem(task_id=task_id, input_data_id=input_id, label="whole", data={"_type": "Classification"})
        for task_id, input_id in [("task1", "input1"), ("task1", "input2"), ("task2", "input1"), ("complete", "input1")]
    ]

    expected_error = failure == "get_task" or (failure == "restore" and role == "accepter")
    with caplog.at_level(logging.INFO), pytest.raises(AnnofabCliException) if expected_error else nullcontext():
        main_obj.create(items, parallelism=parallelism)

    expected_updates = [("task2", "input1")] if failure == "get_task" else [("task1", "input1"), ("task1", "input2"), ("task2", "input1")]
    assert sorted(updates) == expected_updates
    assert [input_id for task_id, input_id in updates if task_id == "task1"] == ([] if failure == "get_task" else ["input1", "input2"])
    for task_id, input_ids in [("task1", ["input1", "input2"]), ("task2", ["input1"])]:
        expected = ["current_operator", *input_ids, "old_operator"] if role == "accepter" else input_ids
        if failure == "get_task" and task_id == "task1":
            expected = []
        assert [event for event_task_id, event in events if event_task_id == task_id] == expected
    assert not (tmp_path / "complete").exists()
    assert "タスクが完了状態" in caplog.text
    assert ("1/4" if failure == "get_task" else "3/4") in caplog.messages[-1]
    if expected_error:
        assert any(record.levelno == logging.WARNING and record.exc_info for record in caplog.records)


def test_parallelism_requires_yes_before_accessing_api() -> None:
    service = Mock()
    args = argparse.Namespace(parallelism=2, yes=False)
    command = CreateAnnotation(service, Mock(), args)

    with pytest.raises(SystemExit) as exc_info:
        command.main()

    assert exc_info.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    service.api.get_annotation_specs.assert_not_called()
