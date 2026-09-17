from __future__ import annotations

import copy
from typing import cast

import annofabapi
import pytest

from annofabcli.annotation.delete_invalid_label_annotation import (
    DeleteInvalidLabelAnnotationMain,
    create_request_body_for_delete_invalid_label_annotation,
    get_existing_label_ids,
)


def create_editor_annotation(details: list[dict]) -> dict:
    return {
        "project_id": "prj1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-06-23T12:00:00+09:00",
        "details": details,
    }


class DummyApi:
    def __init__(self, editor_annotation: dict, *, over_limit: bool = False) -> None:
        self.editor_annotation = editor_annotation
        self.over_limit = over_limit
        self.request_body: list[dict] | None = None

    def get_editor_annotation(self, project_id: str, task_id: str, input_data_id: str, query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert task_id == "task1"
        assert input_data_id == "input1"
        assert query_params == {"v": "2"}
        return self.editor_annotation, None

    def batch_update_annotations(self, project_id: str, request_body: list[dict], query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert query_params == {"v": "2"}
        self.request_body = copy.deepcopy(request_body)
        return {}, None

    def get_tasks(self, project_id: str, query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert query_params == {"page": 1, "limit": 1}
        return {
            "over_limit": self.over_limit,
            "list": [],
            "page_no": 1,
            "total_page_no": 1,
        }, None


class DummyService:
    def __init__(self, editor_annotation: dict, *, over_limit: bool = False) -> None:
        self.api = DummyApi(editor_annotation, over_limit=over_limit)
        self.wrapper: DummyWrapper | None = None


class DummyWrapper:
    def __init__(self, task_list: list[dict]) -> None:
        self.task_list = task_list

    def get_all_tasks(self, project_id: str) -> list[dict]:
        assert project_id == "prj1"
        return self.task_list


class TestGetExistingLabelIds:
    def test_get_existing_label_ids(self) -> None:
        annotation_specs = {
            "labels": [
                {"label_id": "label1"},
                {"label_id": "label2"},
            ]
        }

        actual = get_existing_label_ids(annotation_specs)

        assert actual == {"label1", "label2"}


class TestCreateRequestBodyForDeleteInvalidLabelAnnotation:
    def test_create_request_body_for_delete_invalid_label_annotation(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [],
                },
                {
                    "annotation_id": "anno2",
                    "label_id": "deleted_label",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [],
                },
            ]
        )

        actual = create_request_body_for_delete_invalid_label_annotation(editor_annotation, existing_label_ids={"label1"})

        assert actual.delete_count == 1
        assert actual.request_body == [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-06-23T12:00:00+09:00",
                "annotation_id": "anno2",
                "_type": "Delete",
            }
        ]

    def test_create_request_body_for_delete_invalid_label_annotation__no_target_annotation(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [],
                }
            ]
        )

        actual = create_request_body_for_delete_invalid_label_annotation(editor_annotation, existing_label_ids={"label1"})

        assert actual.delete_count == 0
        assert actual.request_body == []


class TestDeleteInvalidLabelAnnotationMain:
    def test_delete_invalid_label_annotation_for_input_data_uses_batch_update_annotations(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "deleted_label",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [],
                }
            ]
        )
        service = DummyService(editor_annotation)
        obj = DeleteInvalidLabelAnnotationMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.delete_invalid_label_annotation_for_input_data("task1", "input1", {"label1"})

        assert actual == 1
        assert service.api.request_body == [
            {
                "project_id": "prj1",
                "task_id": "task1",
                "input_data_id": "input1",
                "updated_datetime": "2026-06-23T12:00:00+09:00",
                "annotation_id": "anno1",
                "_type": "Delete",
            }
        ]

    def test_delete_invalid_label_annotation_for_input_data__valid_label_does_not_call_batch_update_annotations(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [],
                }
            ]
        )
        service = DummyService(editor_annotation)
        obj = DeleteInvalidLabelAnnotationMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.delete_invalid_label_annotation_for_input_data("task1", "input1", {"label1"})

        assert actual == 0
        assert service.api.request_body is None

    def test_get_target_task_id_list_returns_argument_when_specified(self) -> None:
        service = DummyService(create_editor_annotation([]))
        service.wrapper = DummyWrapper([{"task_id": "task1"}])
        obj = DeleteInvalidLabelAnnotationMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.get_target_task_id_list(["task2"])

        assert actual == ["task2"]

    def test_get_target_task_id_list_returns_all_tasks_when_task_id_is_none(self) -> None:
        service = DummyService(create_editor_annotation([]))
        service.wrapper = DummyWrapper([{"task_id": "task1"}, {"task_id": "task2"}])
        obj = DeleteInvalidLabelAnnotationMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.get_target_task_id_list(None)

        assert actual == ["task1", "task2"]

    def test_get_target_task_id_list_raises_when_task_count_is_over_limit(self) -> None:
        service = DummyService(create_editor_annotation([]), over_limit=True)
        service.wrapper = DummyWrapper([{"task_id": "task1"}])
        obj = DeleteInvalidLabelAnnotationMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        with pytest.raises(ValueError):
            obj.get_target_task_id_list(None)
