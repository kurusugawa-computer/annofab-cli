import json
from pathlib import Path
from typing import Any, cast

import annofabapi
import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus
from annofabapi.parser import (
    SimpleAnnotationDirParser,
    SimpleAnnotationParserByTask,
)
from pydantic import ValidationError

from annofabcli.annotation.editor_props import validate_editor_props_for_cli
from annofabcli.annotation.import_annotation import AnnotationConverter, ImportAnnotationMain, ImportedSimpleAnnotation, ImportedSimpleAnnotationDetail
from annofabcli.common.facade import TaskQuery

service = annofabapi.build()

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text(encoding="utf-8"))

project: dict[str, Any] = {
    "project_id": "9804e9a1-9485-48cf-91a6-e71e810771a4",
    "input_data_type": "image",
    "configuration": {
        "plugin_id": None,
    },
}


class _FakeApi:
    account_id = "account_id"

    def __init__(self, project_member_role: ProjectMemberRole) -> None:
        self.project_member_role = project_member_role

    def get_my_member_in_project(self, _project_id: str) -> tuple[dict[str, str], None]:
        return {"member_role": self.project_member_role.value}, None


class _FakeWrapper:
    def __init__(self, task: dict[str, Any]) -> None:
        self.task = {
            "project_id": project["project_id"],
            "phase_stage": 0,
            "input_data_id_list": [],
            "histories_by_phase": [],
            "work_time_span": 0,
            "number_of_rejections": 0,
            "started_datetime": None,
            "operation_updated_datetime": None,
            "sampling": None,
            "metadata": {},
            **task,
        }
        self.changed_operator_account_ids: list[str | None] = []

    def get_task_or_none(self, _project_id: str, _task_id: str) -> dict[str, Any]:
        return self.task

    def change_task_operator(self, _project_id: str, _task_id: str, operator_account_id: str | None, *, last_updated_datetime: str) -> dict[str, Any]:
        self.changed_operator_account_ids.append(operator_account_id)
        self.task = {**self.task, "account_id": operator_account_id, "updated_datetime": last_updated_datetime}
        return self.task


class _FakeService:
    def __init__(self, task: dict[str, Any], project_member_role: ProjectMemberRole) -> None:
        self.api = _FakeApi(project_member_role)
        self.wrapper = _FakeWrapper(task)


class _FakeTaskParser:
    task_id = "task_id"


class _TestImportAnnotationMain(ImportAnnotationMain):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
        change_operator_to_me: bool,
        is_merge: bool,
        is_overwrite: bool,
        include_complete_task: bool,
        include_break_task: bool,
        include_on_hold_task: bool,
        converter: AnnotationConverter,
    ) -> None:
        super().__init__(
            service,
            project_id=project_id,
            all_yes=all_yes,
            change_operator_to_me=change_operator_to_me,
            is_merge=is_merge,
            is_overwrite=is_overwrite,
            include_complete_task=include_complete_task,
            include_break_task=include_break_task,
            include_on_hold_task=include_on_hold_task,
            converter=converter,
        )
        self.fake_wrapper = cast(_FakeWrapper, service.wrapper)
        self.confirm_processing_called = False
        self.put_annotation_for_task_called = False

    def confirm_processing(self, confirm_message: str) -> bool:
        self.confirm_processing_called = True
        return super().confirm_processing(confirm_message)

    def put_annotation_for_task(self, _task_parser: SimpleAnnotationParserByTask) -> tuple[int, int]:
        self.put_annotation_for_task_called = True
        return 1, 1


def _create_import_annotation_main(
    *, task: dict[str, Any], project_member_role: ProjectMemberRole, change_operator_to_me: bool = False, task_query: TaskQuery | None = None
) -> _TestImportAnnotationMain:
    main_obj = _TestImportAnnotationMain(
        cast(annofabapi.Resource, _FakeService(task, project_member_role)),
        project_id=project["project_id"],
        all_yes=True,
        change_operator_to_me=change_operator_to_me,
        is_merge=False,
        is_overwrite=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        converter=cast(AnnotationConverter, None),
    )
    main_obj.task_query = task_query
    return main_obj


class Test__ImportAnnotationMain:
    def test__execute_task__task_queryの条件に一致しないタスクは問い合わせ前にスキップする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(
            task=task,
            project_member_role=ProjectMemberRole.OWNER,
            task_query=TaskQuery(status=TaskStatus.ON_HOLD),
        )

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert not actual
        assert not obj.confirm_processing_called
        assert not obj.put_annotation_for_task_called

    def test__execute_task__task_queryの担当者条件に一致するタスクをインポートする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(
            task=task,
            project_member_role=ProjectMemberRole.OWNER,
            task_query=TaskQuery(account_id="account_id"),
        )

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert actual
        assert obj.confirm_processing_called
        assert obj.put_annotation_for_task_called

    def test__execute_task__チェッカーが担当者を変更しない場合は問い合わせ前にスキップする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(task=task, project_member_role=ProjectMemberRole.ACCEPTER, change_operator_to_me=False)

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert not actual
        assert not obj.confirm_processing_called
        assert not obj.put_annotation_for_task_called

    def test__execute_task__オーナーは担当者を変更せずにインポートする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(task=task, project_member_role=ProjectMemberRole.OWNER, change_operator_to_me=True)

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert actual
        assert obj.confirm_processing_called
        assert obj.put_annotation_for_task_called
        assert obj.fake_wrapper.changed_operator_account_ids == []

    def test__execute_task__担当者であるチェッカーは担当者を変更せずにインポートする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(task=task, project_member_role=ProjectMemberRole.ACCEPTER, change_operator_to_me=False)

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert actual
        assert obj.confirm_processing_called
        assert obj.put_annotation_for_task_called
        assert obj.fake_wrapper.changed_operator_account_ids == []

    def test__execute_task__未割り当てタスクに担当者変更なしでインポートする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": None,
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(task=task, project_member_role=ProjectMemberRole.ACCEPTER, change_operator_to_me=False)

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert actual
        assert obj.confirm_processing_called
        assert obj.put_annotation_for_task_called
        assert obj.fake_wrapper.changed_operator_account_ids == []

    def test__execute_task__チェッカーは担当者を一時的に変更してインポートする(self):
        task = {
            "task_id": "task_id",
            "phase": "annotation",
            "status": TaskStatus.NOT_STARTED.value,
            "account_id": "other_account_id",
            "updated_datetime": "2026-07-30T00:00:00.000+09:00",
        }
        obj = _create_import_annotation_main(task=task, project_member_role=ProjectMemberRole.ACCEPTER, change_operator_to_me=True)

        actual = obj.execute_task(cast(SimpleAnnotationParserByTask, _FakeTaskParser()))

        assert actual
        assert obj.confirm_processing_called
        assert obj.put_annotation_for_task_called
        assert obj.fake_wrapper.changed_operator_account_ids == ["account_id", "other_account_id"]


class Test__AnnotationConverter:
    def test__convert_annotation_details__既存属性を維持して指定した属性だけ更新する(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        car_label_id = "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"
        traffic_lane_definition_id = "ec27de5d-122c-40e7-89bc-5500e37bae6a"
        occluded_definition_id = "2517f635-2269-4142-8ef4-16312b4cc9f7"
        details = [
            ImportedSimpleAnnotationDetail(
                label="car",
                annotation_id="annotation_id",
                data={"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 30, "y": 40}},
                attributes={"traffic_lane": 3},
            )
        ]
        old_details = [
            {
                "annotation_id": "annotation_id",
                "label_id": car_label_id,
                "additional_data_list": [
                    {"definition_id": traffic_lane_definition_id, "value": {"_type": "Integer", "value": 1}},
                    {"definition_id": occluded_definition_id, "value": {"_type": "Flag", "value": True}},
                ],
            }
        ]

        actual = converter.convert_annotation_details(SimpleAnnotationDirParser(Path("foo.json")), details, old_details)

        assert actual["details"][0]["additional_data_list"] == [
            {"definition_id": traffic_lane_definition_id, "value": {"_type": "Integer", "value": 3}},
            {"definition_id": occluded_definition_id, "value": {"_type": "Flag", "value": True}},
        ]

    def test__convert_annotation_details__nullの属性を削除する(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        car_label_id = "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"
        traffic_lane_definition_id = "ec27de5d-122c-40e7-89bc-5500e37bae6a"
        occluded_definition_id = "2517f635-2269-4142-8ef4-16312b4cc9f7"
        details = [
            ImportedSimpleAnnotationDetail(
                label="car",
                annotation_id="annotation_id",
                data={"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 30, "y": 40}},
                attributes={"occluded": None},
            )
        ]
        old_details = [
            {
                "annotation_id": "annotation_id",
                "label_id": car_label_id,
                "additional_data_list": [
                    {"definition_id": traffic_lane_definition_id, "value": {"_type": "Integer", "value": 1}},
                    {"definition_id": occluded_definition_id, "value": {"_type": "Flag", "value": True}},
                ],
            }
        ]

        actual = converter.convert_annotation_details(SimpleAnnotationDirParser(Path("foo.json")), details, old_details)

        assert actual["details"][0]["additional_data_list"] == [
            {"definition_id": traffic_lane_definition_id, "value": {"_type": "Integer", "value": 1}},
        ]

    def test__convert_annotation_details__ラベル変更時は新ラベルに紐づかない既存属性を削除する(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        car_label_id = "9d6cca8d-3f5a-4808-a6c9-0ae18a478176"
        number_plate_label_id = "39d05700-7c12-4732-bc35-02d65367cc3e"
        traffic_lane_definition_id = "ec27de5d-122c-40e7-89bc-5500e37bae6a"
        number_plate_definition_id = "15ba8b9d-4882-40c2-bb31-ed3f68197c2e"
        details = [
            ImportedSimpleAnnotationDetail(
                label="number_plate",
                annotation_id="annotation_id",
                data={"_type": "BoundingBox", "left_top": {"x": 10, "y": 20}, "right_bottom": {"x": 30, "y": 40}},
                attributes={},
            )
        ]
        old_details = [
            {
                "annotation_id": "annotation_id",
                "label_id": car_label_id,
                "additional_data_list": [
                    {"definition_id": traffic_lane_definition_id, "value": {"_type": "Integer", "value": 1}},
                    {"definition_id": number_plate_definition_id, "value": None},
                ],
            }
        ]

        actual = converter.convert_annotation_details(SimpleAnnotationDirParser(Path("foo.json")), details, old_details)

        assert actual["details"][0]["label_id"] == number_plate_label_id
        assert actual["details"][0]["additional_data_list"] == [{"definition_id": number_plate_definition_id, "value": None}]

    def test__convert_annotation_details__annotation_idを省略した分類アノテーションは既存アノテーションを更新する(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        classification_label_id = "fcb847a5-5607-4467-a72b-fc11fb5cfbab"
        details = [
            ImportedSimpleAnnotationDetail(
                label="whole",
                data={"_type": "Classification"},
            )
        ]
        old_details = [
            {
                "annotation_id": classification_label_id,
                "label_id": classification_label_id,
            }
        ]

        actual = converter.convert_annotation_details(
            SimpleAnnotationDirParser(Path("foo.json")),
            details,
            old_details,
        )

        assert actual["details"] == [
            {
                "_type": "Update",
                "label_id": classification_label_id,
                "annotation_id": classification_label_id,
                "additional_data_list": [],
                "editor_props": {},
                "body": {"_type": "Inner", "data": {"_type": "Classification"}},
            }
        ]

    def test__convert_annotation_details__実効annotation_idが重複する場合は例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        details = [
            ImportedSimpleAnnotationDetail(label="whole", data={"_type": "Classification"}),
            ImportedSimpleAnnotationDetail(label="whole", data={"_type": "Classification"}),
        ]

        with pytest.raises(ValueError):
            converter.convert_annotation_details(
                SimpleAnnotationDirParser(Path("foo.json")),
                details,
                old_details=[],
            )

    def test_xxx(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        parser = SimpleAnnotationDirParser(Path("tests/data/annotation/import_annotation/image_annotation.json"))
        simple_annotation: ImportedSimpleAnnotation = ImportedSimpleAnnotation.from_dict(parser.load_json())
        actual = converter.convert_annotation_details(parser=parser, details=simple_annotation.details, old_details=[], updated_datetime=None)
        expected = {
            "project_id": "9804e9a1-9485-48cf-91a6-e71e810771a4",
            "task_id": "import_annotation",
            "input_data_id": "image_annotation",
            "details": [
                {
                    "_type": "Create",
                    "label_id": "7391e5f4-38e9-4660-85b9-3d908506634c",
                    "annotation_id": "61637acf-4b95-45d6-9954-d88195547cec",
                    "additional_data_list": [],
                    "editor_props": {},
                    "body": {
                        "_type": "Inner",
                        "data": {"points": [{"x": 1968, "y": 828}, {"x": 1629, "y": 448}, {"x": 2037, "y": 414}], "_type": "Points"},
                    },
                },
                {
                    "_type": "Create",
                    "label_id": "afc8ffef-ce87-463d-bf62-070771465438",
                    "annotation_id": "7bef9886-5e3f-4d86-8749-6220dc93ec74",
                    "additional_data_list": [],
                    "editor_props": {},
                    "body": {
                        "_type": "Inner",
                        "data": {"points": [{"x": 1857, "y": 467}, {"x": 1732, "y": 870}, {"x": 2196, "y": 928}], "_type": "Points"},
                    },
                },
                {
                    "_type": "Create",
                    "label_id": "39d05700-7c12-4732-bc35-02d65367cc3e",
                    "annotation_id": "5152a850-8357-4933-9f58-511d2974cf44",
                    "additional_data_list": [{"definition_id": "15ba8b9d-4882-40c2-bb31-ed3f68197c2e", "value": None}],
                    "editor_props": {},
                    "body": {
                        "_type": "Inner",
                        "data": {"left_top": {"x": 1382, "y": 753}, "right_bottom": {"x": 1565, "y": 945}, "_type": "BoundingBox"},
                    },
                },
                {
                    "_type": "Create",
                    "label_id": "9d6cca8d-3f5a-4808-a6c9-0ae18a478176",
                    "annotation_id": "67c0c3df-c90d-4e62-aa5e-a5db3998c1af",
                    "additional_data_list": [
                        {"definition_id": "e771ac4b-97d1-4af3-ba4b-f0e5b22e8648", "value": {"_type": "Flag", "value": True}},
                        {"definition_id": "69a20a12-ef5f-446f-a03e-0c4ab487ff90", "value": {"_type": "Select", "choice_id": "stopping"}},
                        {"definition_id": "9b05648d-1e16-4ea2-ab79-48907f5eed00", "value": {"_type": "Text", "value": "test"}},
                        {"definition_id": "2517f635-2269-4142-8ef4-16312b4cc9f7", "value": {"_type": "Flag", "value": True}},
                        {"definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a", "value": {"_type": "Integer", "value": 3}},
                        {
                            "definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                            "value": {"_type": "Choice", "choice_id": "7512ee39-8073-4e24-9b8c-93d99b76b7d2"},
                        },
                        {
                            "definition_id": "d52230b3-f258-4d0c-993e-533450164e81",
                            "value": {"_type": "Link", "annotation_id": "5152a850-8357-4933-9f58-511d2974cf44"},
                        },
                        {
                            "definition_id": "d349e76d-b59a-44cd-94b4-713a00b2e84d",
                            "value": {"_type": "Tracking", "value": "67c0c3df-c90d-4e62-aa5e-a5db3998c1af"},
                        },
                        {"definition_id": "2fa239c6-94d7-4383-9a8e-7a40f9e7a068", "value": {"_type": "Comment", "value": "aaaaa"}},
                    ],
                    "editor_props": {},
                    "body": {
                        "_type": "Inner",
                        "data": {"left_top": {"x": 626, "y": 217}, "right_bottom": {"x": 1262, "y": 620}, "_type": "BoundingBox"},
                    },
                },
                {
                    "_type": "Create",
                    "label_id": "fcb847a5-5607-4467-a72b-fc11fb5cfbab",
                    "annotation_id": "fcb847a5-5607-4467-a72b-fc11fb5cfbab",
                    "additional_data_list": [
                        {
                            "definition_id": "fff3fcc3-093d-41ce-90cf-b4d9b2688b78",
                            "value": {"_type": "Choice", "choice_id": "c557a034-1abc-479a-bed3-3a33c006a195"},
                        }
                    ],
                    "editor_props": {},
                    "body": {"_type": "Inner", "data": {"_type": "Classification"}},
                },
            ],
            "updated_datetime": None,
            "format_version": "2.0.0",
        }
        assert actual == expected

    def test__convert_annotation_detail__基本(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        detail = ImportedSimpleAnnotationDetail(
            label="car",
            data={"left_top": {"x": 10, "y": 7}, "right_bottom": {"x": 36, "y": 36}, "_type": "BoundingBox"},
            attributes={"traffic_lane": 3, "occluded": True},
            annotation_id=None,
        )
        actual = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), detail)
        expected = {
            "_type": "Create",
            "label_id": "b6e6e2e2-2e7c-4e2e-8e2e-2e7c4e2e8e2e",  # annotation_specs.jsonのcarラベルIDに合わせて修正が必要
            "annotation_id": "random_id",
            "additional_data_list": [
                {"definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a", "value": {"_type": "Integer", "value": 3}},
                {"definition_id": "2517f635-2269-4142-8ef4-16312b4cc9f7", "value": {"_type": "Flag", "value": True}},
            ],
            "editor_props": {},
            "body": {"_type": "Inner", "data": {"left_top": {"x": 10, "y": 7}, "right_bottom": {"x": 36, "y": 36}, "_type": "BoundingBox"}},
        }
        # label_idはannotation_specs.jsonの内容に依存するため、実際の値でassert
        assert actual["_type"] == expected["_type"]
        assert actual["additional_data_list"] == expected["additional_data_list"]
        assert actual["editor_props"] == expected["editor_props"]
        assert actual["body"] == expected["body"]

    def test__convert_annotation_detail__2d座標値がfloatならroundでintに変換する(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)

        bbox_detail = ImportedSimpleAnnotationDetail(
            label="car",
            data={"left_top": {"x": 10.4, "y": 7.5}, "right_bottom": {"x": 36.6, "y": 36.0}, "_type": "BoundingBox"},
            attributes={},
        )
        actual_bbox = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), bbox_detail)
        assert actual_bbox["body"]["data"] == {"left_top": {"x": 10, "y": 8}, "right_bottom": {"x": 37, "y": 36}, "_type": "BoundingBox"}
        assert bbox_detail.data["left_top"]["x"] == 10.4

        points_detail = ImportedSimpleAnnotationDetail(
            label="white_line",
            data={"points": [{"x": 1.2, "y": 2.8}, {"x": 3.0, "y": 4.4}], "_type": "Points"},
            attributes={},
        )
        actual_points = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), points_detail)
        assert actual_points["body"]["data"] == {"points": [{"x": 1, "y": 3}, {"x": 3, "y": 4}], "_type": "Points"}

        single_point_detail = ImportedSimpleAnnotationDetail(
            label="car",
            data={"point": {"x": 5.5, "y": 6.1}, "_type": "SinglePoint"},
            attributes={},
        )
        actual_single_point = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), single_point_detail)
        assert actual_single_point["body"]["data"] == {"point": {"x": 6, "y": 6}, "_type": "SinglePoint"}

    def test__convert_annotation_detail__default_editor_propsを設定する(self):
        converter = AnnotationConverter(
            project,
            annotation_specs,
            is_strict=False,
            service=service,
            default_editor_props={"can_delete": False, "can_edit_data": False, "can_edit_additional": False},
        )
        detail = ImportedSimpleAnnotationDetail(
            label="car",
            data={"left_top": {"x": 10, "y": 7}, "right_bottom": {"x": 36, "y": 36}, "_type": "BoundingBox"},
            attributes={},
            annotation_id="annotation_id",
        )
        actual = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), detail)
        assert actual["editor_props"] == {
            "can_delete": False,
            "can_edit_data": False,
            "can_edit_additional": False,
        }

    def test__convert_annotation_detail__detailのeditor_propsはdefault_editor_propsにマージされる(self):
        converter = AnnotationConverter(
            project,
            annotation_specs,
            is_strict=False,
            service=service,
            default_editor_props={"can_delete": False, "can_edit_data": False},
        )
        detail = ImportedSimpleAnnotationDetail(
            label="car",
            data={"left_top": {"x": 10, "y": 7}, "right_bottom": {"x": 36, "y": 36}, "_type": "BoundingBox"},
            attributes={},
            annotation_id="annotation_id",
            editor_props={"can_delete": True, "tags": ["imported"]},
        )
        actual = converter.convert_annotation_detail(SimpleAnnotationDirParser(Path("foo.json")), detail)
        assert actual["editor_props"] == {"can_delete": True, "can_edit_data": False, "tags": ["imported"]}

    def test__validate_editor_props__schema違反なら例外(self):
        with pytest.raises(ValidationError):
            validate_editor_props_for_cli({"can_delete": "false"})

    def test__validate_editor_props__CLIで対応していないキーなら例外(self):
        with pytest.raises(ValidationError):
            validate_editor_props_for_cli({"description": "未対応"})

    def test__convert_attributes__期待通りの値が格納されている(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        actual = converter.convert_attributes(
            attributes={
                "traffic_lane": 3,
                "car_kind": "emergency_vehicle",
                "condition": "running",
                "occluded": True,
                "note": "foo",
                "status": "bar",
                "number_plate": "anno_id1",
            }
        )
        expected = [
            {"definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a", "value": {"_type": "Integer", "value": 3}},
            {
                "definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2",
                "value": {"_type": "Choice", "choice_id": "c07f9702-4760-4e7c-824d-b87bac356a80"},
            },
            {"definition_id": "69a20a12-ef5f-446f-a03e-0c4ab487ff90", "value": {"_type": "Select", "choice_id": "running"}},
            {"definition_id": "2517f635-2269-4142-8ef4-16312b4cc9f7", "value": {"_type": "Flag", "value": True}},
            {"definition_id": "9b05648d-1e16-4ea2-ab79-48907f5eed00", "value": {"_type": "Text", "value": "foo"}},
            {"definition_id": "2fa239c6-94d7-4383-9a8e-7a40f9e7a068", "value": {"_type": "Comment", "value": "bar"}},
            {"definition_id": "d52230b3-f258-4d0c-993e-533450164e81", "value": {"_type": "Link", "annotation_id": "anno_id1"}},
        ]
        assert actual == expected

    def test__convert_attributes__存在しない属性名はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        actual = converter.convert_attributes(
            attributes={
                "traffic_lane": 3,
                "not_exist_attr": "xxx",  # 存在しない属性
            }
        )
        # "traffic_lane"のみ変換される
        assert actual == [
            {"definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a", "value": {"_type": "Integer", "value": 3}},
        ]

    def test__convert_attributes__存在しない属性名はis_strict_trueなら例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=True, service=service)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "traffic_lane": 3,
                    "not_exist_attr": "xxx",
                }
            )

    def test__convert_attributes__int属性の型不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        # "traffic_lane"はint型だがstrを渡す
        actual = converter.convert_attributes(
            attributes={
                "traffic_lane": "not_int",
            }
        )
        assert actual == [
            {"definition_id": "ec27de5d-122c-40e7-89bc-5500e37bae6a", "value": None},
        ]

    def test__convert_attributes__int属性の型不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=True, service=service)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "traffic_lane": "not_int",
                }
            )

    def test__convert_attributes__bool属性の型不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        # "occluded"はbool型だがstrを渡す
        actual = converter.convert_attributes(
            attributes={
                "occluded": "not_bool",
            }
        )
        assert actual == [
            {"definition_id": "2517f635-2269-4142-8ef4-16312b4cc9f7", "value": None},
        ]

    def test__convert_attributes__bool属性の型不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=True, service=service)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "occluded": "not_bool",
                }
            )

    def test__convert_attributes__radiobutton属性の選択肢不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        actual = converter.convert_attributes(
            attributes={
                "car_kind": "not_exist_choice",
            }
        )
        assert actual == [
            {"definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2", "value": None},
        ]

    def test__convert_attributes__radiobutton属性の選択肢不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=True, service=service)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "car_kind": "not_exist_choice",
                }
            )

    def test__convert_attributes__dropdown属性の選択肢不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=False, service=service)
        actual = converter.convert_attributes(
            attributes={
                "condition": "not_exist_choice",
            }
        )
        assert actual == [
            {"definition_id": "69a20a12-ef5f-446f-a03e-0c4ab487ff90", "value": None},
        ]

    def test__convert_attributes__dropdown属性の選択肢不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(project, annotation_specs, is_strict=True, service=service)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "condition": "not_exist_choice",
                }
            )
