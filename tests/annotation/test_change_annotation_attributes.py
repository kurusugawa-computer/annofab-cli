from unittest.mock import Mock

import pytest

from annofabcli.annotation.annotation_query import AnnotationQueryForAPI
from annofabcli.annotation.change_annotation_attributes import ChangeAnnotationAttributesMain


@pytest.mark.parametrize("task_id_list", [[], ["task1", "task2"]])
def test_explicit_task_ids_do_not_fetch_all_tasks(task_id_list: list[str]) -> None:
    service = Mock()
    main_obj = ChangeAnnotationAttributesMain(service, project_id="prj1", include_complete_task=False, all_yes=True)

    assert main_obj.get_target_task_id_list(task_id_list) == task_id_list
    service.wrapper.get_all_tasks.assert_not_called()


def test_missing_target_does_not_fetch_or_update_annotations() -> None:
    service = Mock()
    main_obj = ChangeAnnotationAttributesMain(service, project_id="prj1", include_complete_task=False, all_yes=True)

    with pytest.raises(ValueError):
        main_obj.change_annotation_attributes_for_task_list(None, AnnotationQueryForAPI(label_id="car"), [])

    service.wrapper.get_all_tasks.assert_not_called()
    service.api.batch_update_annotations.assert_not_called()


def test_all_tasks_limit_aborts_before_updates() -> None:
    service = Mock()
    service.wrapper.get_all_tasks.return_value = [{"task_id": "task1"}] * 10_000
    main_obj = ChangeAnnotationAttributesMain(service, project_id="prj1", include_complete_task=False, all_yes=True)

    with pytest.raises(ValueError):
        main_obj.change_annotation_attributes_for_task_list(None, AnnotationQueryForAPI(label_id="car"), [], all_tasks=True)

    service.wrapper.get_task_or_none.assert_not_called()
    service.api.batch_update_annotations.assert_not_called()


@pytest.mark.parametrize("task_ids", [[], ["task1", "task2"]])
def test_all_tasks_updates_attributes(task_ids: list[str]) -> None:
    service = Mock()
    service.wrapper.get_all_tasks.return_value = [{"task_id": task_id} for task_id in task_ids]
    service.api.get_project.return_value = ({"title": "project1"}, None)
    service.api.batch_update_annotations.return_value = ([], None)
    task = {
        "project_id": "prj1",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
        "input_data_id_list": ["input1"],
        "account_id": None,
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2026-10-09T00:00:00+09:00",
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": None,
    }
    service.wrapper.get_task_or_none.side_effect = [{**task, "task_id": task_id} for task_id in task_ids]
    service.wrapper.get_all_annotation_list.side_effect = [
        [{"project_id": "prj1", "task_id": task_id, "input_data_id": "input1", "updated_datetime": task["updated_datetime"], "detail": {"annotation_id": "anno1", "label_id": "car"}}]
        for task_id in task_ids
    ]
    main_obj = ChangeAnnotationAttributesMain(service, project_id="prj1", include_complete_task=False, all_yes=True)
    attributes = [{"additional_data_definition_id": "occluded", "value": False}]

    main_obj.change_annotation_attributes_for_task_list(None, AnnotationQueryForAPI(label_id="car"), attributes, all_tasks=True)

    updates = service.api.batch_update_annotations.call_args_list
    assert [call.kwargs["request_body"][0]["data"]["task_id"] for call in updates] == task_ids
    assert all(call.kwargs["request_body"][0]["data"]["additional_data_list"] == attributes for call in updates)


@pytest.mark.parametrize("include_on_hold_task", [False, True])
def test_on_hold_task_requires_explicit_opt_in(include_on_hold_task: bool) -> None:  # noqa: FBT001
    service = Mock()
    task = {
        "project_id": "project1",
        "task_id": "task1",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "on_hold",
        "input_data_id_list": ["input1"],
        "account_id": None,
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2026-10-09T00:00:00+09:00",
        "operation_updated_datetime": None,
        "sampling": None,
        "metadata": None,
    }
    service.wrapper.get_task_or_none.return_value = task
    service.wrapper.get_all_annotation_list.return_value = []
    obj = ChangeAnnotationAttributesMain(service, project_id="project1", include_complete_task=False, include_on_hold_task=include_on_hold_task, all_yes=True)
    obj.change_attributes_for_task("task1", annotation_query=AnnotationQueryForAPI(label_id="car"), additional_data_list=[])
    assert service.wrapper.get_all_annotation_list.called is include_on_hold_task
    service.api.batch_update_annotations.assert_not_called()
