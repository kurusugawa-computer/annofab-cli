import argparse
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.create_classification_annotation import CreateClassificationAnnotation, CreateClassificationAnnotationMain


@pytest.fixture
def service() -> Mock:
    service = Mock()
    service.api.account_id = "account_id"
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    specs = {
        "labels": [
            {
                "label_id": name,
                "label_name": {"messages": [{"lang": "en-US", "message": name}], "default_lang": "en-US"},
                "annotation_type": "classification",
                "additional_data_definitions": [f"{name}-sunny"],
            }
            for name in ["weather", "season"]
        ],
        "additionals": [
            {
                "additional_data_definition_id": f"{name}-sunny",
                "name": {"messages": [{"lang": "en-US", "message": "sunny"}], "default_lang": "en-US"},
                "type": "flag",
                "choices": [],
            }
            for name in ["weather", "season"]
        ],
        "inspection_phrases": [],
    }
    service.api.get_annotation_specs.return_value = (specs, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "phase": "annotation",
        "status": TaskStatus.NOT_STARTED.value,
        "account_id": "account_id",
        "updated_datetime": "2026-10-12T00:00:00+09:00",
        "input_data_id_list": ["input1", "input2"],
    }
    service.api.get_editor_annotations_in_bulk.return_value = (
        {
            "success": [{"input_data_id": input_data_id, "details": [], "updated_datetime": "2026-10-12T00:00:00+09:00"} for input_data_id in ["input1", "input2"]],
            "failure": [],
        },
        None,
    )
    return service


def make_main(service: Mock) -> CreateClassificationAnnotationMain:
    return CreateClassificationAnnotationMain(
        service,
        project_id="prj1",
        all_yes=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )


@pytest.mark.parametrize("attributes", [None, {}, {"sunny": True}, {"sunny": False}, {"sunny": None}])
def test_main__新規作成する各入力データに属性値を設定する(service: Mock, attributes):
    make_main(service).main(["task1"], ["weather"], attributes=attributes)

    calls = service.api.put_annotation.call_args_list
    assert len(calls) == 2
    expected_attributes = [] if not attributes else [{"definition_id": "weather-sunny", "value": None if attributes["sunny"] is None else {"_type": "Flag", "value": attributes["sunny"]}}]
    for call in calls:
        detail = call.kwargs["request_body"]["details"][0]
        assert detail["annotation_id"] == "weather"
        assert detail["additional_data_list"] == expected_attributes


def test_main__既存の全体アノテーションを更新しない(service: Mock):
    existing_detail = {"annotation_id": "weather", "label_id": "weather", "additional_data_list": [{"definition_id": "weather-sunny", "value": {"_type": "Flag", "value": False}}]}
    original_detail = deepcopy(existing_detail)
    service.api.get_editor_annotations_in_bulk.return_value[0]["success"][0]["details"] = [existing_detail]

    make_main(service).main(["task1"], ["weather"], attributes={"sunny": True})

    assert service.api.put_annotation.call_count == 1
    assert service.api.put_annotation.call_args.args[2] == "input2"
    assert existing_detail == original_detail


@pytest.mark.parametrize(("labels", "attributes"), [(["weather", "season"], {}), (["missing"], {}), (["weather"], {"unknown": True})])
def test_main__不正な属性指定ではタスクを操作しない(service: Mock, labels, attributes):
    with pytest.raises(ValueError):
        make_main(service).main(["task1"], labels, attributes=attributes)

    service.wrapper.get_task_or_none.assert_not_called()
    service.api.put_annotation.assert_not_called()


def test_main__属性値を指定しない場合は複数ラベルを作成できる(service: Mock):
    make_main(service).main(["task1"], ["weather", "season"])

    details = service.api.put_annotation.call_args.kwargs["request_body"]["details"]
    assert [detail["annotation_id"] for detail in details] == ["weather", "season"]
    assert all(detail["additional_data_list"] == [] for detail in details)


@pytest.mark.parametrize("from_file", [False, True])
def test_command__JSONとファイルから属性値を指定できる(service: Mock, tmp_path: Path, *, from_file: bool):
    attributes_json = json.dumps({"sunny": True})
    if from_file:
        attributes_path = tmp_path / "attributes.json"
        attributes_path.write_text(attributes_json, encoding="utf-8")
        attributes_json = f"file://{attributes_path}"
    args = argparse.Namespace(
        project_id="prj1",
        task_id=["task1"],
        label_name=["weather"],
        attributes=attributes_json,
        parallelism=None,
        yes=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    CreateClassificationAnnotation(service, Mock(), args).main()

    detail = service.api.put_annotation.call_args.kwargs["request_body"]["details"][0]
    assert detail["additional_data_list"] == [{"definition_id": "weather-sunny", "value": {"_type": "Flag", "value": True}}]


def test_main__画像全体以外のラベルに属性値を指定できない(service: Mock):
    service.api.get_annotation_specs.return_value[0]["labels"][0]["annotation_type"] = "bounding_box"

    with pytest.raises(ValueError):
        make_main(service).main(["task1"], ["weather"], attributes={"sunny": True})

    service.wrapper.get_task_or_none.assert_not_called()
    service.api.put_annotation.assert_not_called()


@pytest.mark.parametrize("attributes_json", ["[]", "null", '{"sunny": []}', '{"sunny": 1.5}', "invalid"])
def test_command__不正なJSON形式では書き込まない(service: Mock, attributes_json: str):
    args = argparse.Namespace(
        project_id="prj1",
        task_id=["task1"],
        label_name=["weather"],
        attributes=attributes_json,
        parallelism=None,
        yes=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    with pytest.raises(SystemExit) as exc:
        CreateClassificationAnnotation(service, Mock(), args).main()

    assert exc.value.code == 2
    service.api.put_annotation.assert_not_called()


def test_create_classification_annotation_for_task__アノテーション情報を取得できない入力データをスキップする():
    service = Mock()
    service.api.account_id = "account_id"
    service.api.get_annotation_specs.return_value = ({"labels": [], "additionals": [], "inspection_phrases": []}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.OWNER.value}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "phase": "annotation",
        "status": TaskStatus.NOT_STARTED.value,
        "account_id": "account_id",
        "updated_datetime": "2026-08-10T00:00:00+09:00",
        "input_data_id_list": ["input1", "input2"],
    }
    service.api.get_editor_annotations_in_bulk.return_value = (
        {"success": [{"input_data_id": "input2", "details": []}], "failure": [{"input_data_id": "input1"}]},
        None,
    )
    service.api.get_editor_annotation.side_effect = RuntimeError()
    obj = CreateClassificationAnnotationMain(
        service,
        project_id="prj1",
        all_yes=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    obj._create_annotation_details_for_labels = Mock(return_value=[])  # type: ignore[method-assign]
    obj._put_annotations_for_input_data = Mock(return_value=0)  # type: ignore[method-assign]

    actual = obj.create_classification_annotation_for_task("task1", ["label1"])

    assert actual == 0
    obj._create_annotation_details_for_labels.assert_called_once()
    assert obj._create_annotation_details_for_labels.call_args.args[:2] == ("task1", "input2")
