import json
from pathlib import Path

import annofabapi
import pytest
from annofabapi.parser import (
    SimpleAnnotationDirParser,
)

from annofabcli.annotation.import_annotation import (
    AnnotationConverter,
    ImportedSimpleAnnotation,
    ImportedSimpleAnnotationDetail,
)

service = annofabapi.build()

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text(encoding="utf-8"))

project = {
    "project_id": "9804e9a1-9485-48cf-91a6-e71e810771a4",
    "input_data_type": "image",
    "configuration": {
        "plugin_id": None,
    },
}


class Test__AnnotationConverter:
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
        # 型不一致なので空リスト
        assert actual == [
            # valueがNoneになるが、definition_idは付与される
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
        # 型不一致なので空リスト
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
