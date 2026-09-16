import argparse
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus

import annofabcli.annotation.create_annotation
from annofabcli.annotation.create_annotation import (
    CreateAnnotationCount,
    CreateAnnotationItem,
    CreateAnnotationMain,
    create_request_body,
    filter_annotation_items_by_task_ids,
    get_annotation_items_from_csv,
)
from annofabcli.annotation.create_annotation_converter import CreateAnnotationConverter

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


def test_create_for_task__別担当のチェッカーは担当者変更オプションなしではスキップする():
    service = Mock()
    service.api.account_id = "my_account_id"
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.ACCEPTER.value}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task_id",
        "status": TaskStatus.NOT_STARTED.value,
        "account_id": "other_account_id",
        "updated_datetime": "2026-08-16T00:00:00+09:00",
    }
    obj = CreateAnnotationMain(
        service,
        project_id="project_id",
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        change_operator_to_me=False,
        all_yes=True,
        converter=Mock(),
        backup_dir=None,
    )

    actual = obj.create_for_task("task_id", {"input_data_id": [Mock()]})

    assert actual == CreateAnnotationCount(success=0, failed=1)
    service.wrapper.change_task_operator.assert_not_called()


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
        change_operator_to_me=False,
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
