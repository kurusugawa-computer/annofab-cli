import json
from pathlib import Path

from annofabcli.annotation.import_annotation import AnnotationConverter

annotation_specs = json.loads(Path("tests/data/annotation/import_annotation/annotation_specs.json").read_text())


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
