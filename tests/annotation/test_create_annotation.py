import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.create_annotation import CreateAnnotationCount, CreateAnnotationItem, CreateAnnotationMain, create_request_body
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


def test_create_for_task__休憩中タスクは既定でスキップする():
    service = Mock()
    service.api.account_id = "my_account_id"
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task_id",
        "status": TaskStatus.BREAK.value,
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

    actual = obj.create_for_task("task_id", {"input_data_id": [Mock()]})

    assert actual == CreateAnnotationCount(success=0, failed=1)
