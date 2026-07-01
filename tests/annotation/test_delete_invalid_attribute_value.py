from __future__ import annotations

import copy
from typing import cast

import annofabapi

from annofabcli.annotation.delete_invalid_attribute_value import (
    DeleteInvalidAttributeValueMain,
    create_request_body_for_delete_attribute_value,
    filter_invalid_additional_data_list,
    get_allowed_attribute_ids_by_label_id,
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
    def __init__(self, editor_annotation: dict) -> None:
        self.editor_annotation = editor_annotation
        self.request_body: dict | None = None

    def get_editor_annotation(self, project_id: str, task_id: str, input_data_id: str, query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert task_id == "task1"
        assert input_data_id == "input1"
        assert query_params == {"v": "2"}
        return self.editor_annotation, None

    def put_annotation(self, project_id: str, task_id: str, input_data_id: str, request_body: dict, query_params: dict) -> tuple[dict, None]:
        assert project_id == "prj1"
        assert task_id == "task1"
        assert input_data_id == "input1"
        assert query_params == {"v": "2"}
        self.request_body = copy.deepcopy(request_body)
        return request_body, None


class DummyService:
    def __init__(self, editor_annotation: dict) -> None:
        self.api = DummyApi(editor_annotation)


class TestFilterInvalidAdditionalDataList:
    def test_filter_invalid_additional_data_list(self) -> None:
        additional_data_list = [
            {"definition_id": "attr1", "value": {"_type": "Text", "value": "foo"}},
            {"definition_id": "attr2", "value": {"_type": "Flag", "value": True}},
            {"definition_id": "attr3", "value": {"_type": "Integer", "value": 1}},
        ]

        actual = filter_invalid_additional_data_list(additional_data_list, {"attr2"})

        assert actual == [{"definition_id": "attr2", "value": {"_type": "Flag", "value": True}}]


class TestGetAllowedAttributeIdsByLabelId:
    def test_get_allowed_attribute_ids_by_label_id(self) -> None:
        annotation_specs = {
            "labels": [
                {"label_id": "label1", "additional_data_definitions": ["attr1", "attr2"]},
                {"label_id": "label2", "additional_data_definitions": ["attr2", "attr3"]},
            ]
        }

        actual = get_allowed_attribute_ids_by_label_id(annotation_specs)

        assert actual == {
            "label1": {"attr1", "attr2"},
            "label2": {"attr2", "attr3"},
        }


class TestCreateRequestBodyForDeleteAttributeValue:
    def test_create_request_body_for_delete_attribute_value(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "foo"}},
                        {"definition_id": "attr2", "value": {"_type": "Flag", "value": True}},
                    ],
                },
                {
                    "annotation_id": "anno2",
                    "label_id": "label2",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr2", "value": {"_type": "Flag", "value": False}},
                        {"definition_id": "attr3", "value": {"_type": "Integer", "value": 2}},
                    ],
                },
                {
                    "annotation_id": "anno3",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [{"definition_id": "attr1", "value": {"_type": "Text", "value": "not-target"}}],
                },
            ]
        )

        actual = create_request_body_for_delete_attribute_value(editor_annotation, allowed_attribute_ids_by_label_id={"label1": {"attr2"}, "label2": {"attr3"}})

        assert actual.count.success == 3
        assert actual.count.skipped == 0
        assert actual.request_body == {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-06-23T12:00:00+09:00",
            "format_version": "2.0.0",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": None,
                    "additional_data_list": [{"definition_id": "attr2", "value": {"_type": "Flag", "value": True}}],
                    "_type": "Update",
                },
                {
                    "annotation_id": "anno2",
                    "label_id": "label2",
                    "body": None,
                    "additional_data_list": [{"definition_id": "attr3", "value": {"_type": "Integer", "value": 2}}],
                    "_type": "Update",
                },
                {
                    "annotation_id": "anno3",
                    "label_id": "label1",
                    "body": None,
                    "additional_data_list": [],
                    "_type": "Update",
                },
            ],
        }

    def test_create_request_body_for_delete_attribute_value__no_target_attribute(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "foo"}},
                    ],
                }
            ]
        )

        actual = create_request_body_for_delete_attribute_value(editor_annotation, allowed_attribute_ids_by_label_id={"label1": {"attr1"}})

        assert actual.count.success == 0
        assert actual.count.skipped == 0

    def test_create_request_body_for_delete_attribute_value__unknown_label_id(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "unknown_label",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "skip"}},
                    ],
                },
                {
                    "annotation_id": "anno2",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "delete"}},
                        {"definition_id": "attr2", "value": {"_type": "Flag", "value": True}},
                    ],
                },
            ]
        )

        actual = create_request_body_for_delete_attribute_value(editor_annotation, allowed_attribute_ids_by_label_id={"label1": {"attr2"}})

        assert actual.count.success == 1
        assert actual.count.skipped == 1
        assert actual.request_body["details"] == [
            {
                "annotation_id": "anno1",
                "label_id": "unknown_label",
                "body": None,
                "additional_data_list": [
                    {"definition_id": "attr1", "value": {"_type": "Text", "value": "skip"}},
                ],
                "_type": "Update",
            },
            {
                "annotation_id": "anno2",
                "label_id": "label1",
                "body": None,
                "additional_data_list": [{"definition_id": "attr2", "value": {"_type": "Flag", "value": True}}],
                "_type": "Update",
            },
        ]


class TestDeleteInvalidAttributeValueMain:
    def test_delete_attribute_value_for_input_data_uses_put_annotation(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "foo"}},
                        {"definition_id": "attr2", "value": {"_type": "Flag", "value": True}},
                    ],
                }
            ]
        )
        service = DummyService(editor_annotation)
        obj = DeleteInvalidAttributeValueMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.delete_attribute_value_for_input_data("task1", "input1", {"label1": {"attr2"}})

        assert actual.success == 1
        assert actual.skipped == 0
        assert service.api.request_body == {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "updated_datetime": "2026-06-23T12:00:00+09:00",
            "format_version": "2.0.0",
            "details": [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": None,
                    "additional_data_list": [{"definition_id": "attr2", "value": {"_type": "Flag", "value": True}}],
                    "_type": "Update",
                }
            ],
        }

    def test_delete_attribute_value_for_input_data__valid_attribute_value_does_not_put_annotation(self) -> None:
        editor_annotation = create_editor_annotation(
            [
                {
                    "annotation_id": "anno1",
                    "label_id": "label1",
                    "body": {"_type": "Inner", "data": {"_type": "BoundingBox"}},
                    "additional_data_list": [
                        {"definition_id": "attr1", "value": {"_type": "Text", "value": "foo"}},
                    ],
                }
            ]
        )
        service = DummyService(editor_annotation)
        obj = DeleteInvalidAttributeValueMain(cast(annofabapi.Resource, service), project_id="prj1", include_complete_task=False, all_yes=True)

        actual = obj.delete_attribute_value_for_input_data("task1", "input1", {"label1": {"attr1"}})

        assert actual.success == 0
        assert actual.skipped == 0
        assert service.api.request_body is None
