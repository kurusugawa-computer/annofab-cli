import json
from pathlib import Path

import pytest

from annofabcli.annotation.import_annotation import AnnotationConverter

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text(encoding="utf-8"))


class Test__AnnotationConverter:
    def test__convert_attributes__期待通りの値が格納されている(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
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
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
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
        converter = AnnotationConverter(None, annotation_specs, is_strict=True)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "traffic_lane": 3,
                    "not_exist_attr": "xxx",
                }
            )

    def test__convert_attributes__int属性の型不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
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
        converter = AnnotationConverter(None, annotation_specs, is_strict=True)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "traffic_lane": "not_int",
                }
            )

    def test__convert_attributes__bool属性の型不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
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
        converter = AnnotationConverter(None, annotation_specs, is_strict=True)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "occluded": "not_bool",
                }
            )

    def test__convert_attributes__radiobutton属性の選択肢不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
        actual = converter.convert_attributes(
            attributes={
                "car_kind": "not_exist_choice",
            }
        )
        assert actual == [
            {"definition_id": "cbb0155f-1631-48e1-8fc3-43c5f254b6f2", "value": None},
        ]

    def test__convert_attributes__radiobutton属性の選択肢不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=True)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "car_kind": "not_exist_choice",
                }
            )

    def test__convert_attributes__dropdown属性の選択肢不一致はis_strict_falseなら無視される(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=False)
        actual = converter.convert_attributes(
            attributes={
                "condition": "not_exist_choice",
            }
        )
        assert actual == [
            {"definition_id": "69a20a12-ef5f-446f-a03e-0c4ab487ff90", "value": None},
        ]

    def test__convert_attributes__dropdown属性の選択肢不一致はis_strict_trueなら例外(self):
        converter = AnnotationConverter(None, annotation_specs, is_strict=True)
        with pytest.raises(ValueError):
            converter.convert_attributes(
                attributes={
                    "condition": "not_exist_choice",
                }
            )
