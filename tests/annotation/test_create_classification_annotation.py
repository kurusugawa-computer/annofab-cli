from unittest.mock import Mock

from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.create_classification_annotation import CreateClassificationAnnotationMain


def test_create_classification_annotation_for_task__アノテーション情報を取得できない入力データをスキップする():
    service = Mock()
    service.api.account_id = "account_id"
    service.api.get_annotation_specs.return_value = ({"labels": [], "additionals": []}, None)
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
