from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from annofabcli.annotation_specs.list_attribute_restriction import FormatArgument, ListAttributeRestrictionMain

data_dir = Path("./tests/data/annotation_specs")
out_dir = Path("./tests/out/annotation_specs")
out_dir.mkdir(exist_ok=True, parents=True)


class TestListAttributeRestrictionMain:
    obj: ListAttributeRestrictionMain
    annotation_specs: dict[str, Any]

    @classmethod
    def setup_class(cls):
        with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
            annotation_specs = json.load(f)

        cls.obj = ListAttributeRestrictionMain(
            labels=annotation_specs["labels"],
            additionals=annotation_specs["additionals"],
            format=FormatArgument.DETAILED_TEXT,
        )
        cls.annotation_specs = annotation_specs

    def test_get_restriction_text__equals(self):
        attribute_id = "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
        condition = {"value": "foo", "_type": "Equals"}
        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert actual == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') EQUALS 'foo'"

    def test_get_restriction_text__equals_dropdown(self):
        attribute_id = "71620647-98cf-48ad-b43b-4af425a24f32"
        condition = {"value": "b690fa1a-7b3d-4181-95d8-f5c75927c3fc", "_type": "Equals"}
        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert (
            actual
            == "'type' (id='71620647-98cf-48ad-b43b-4af425a24f32', type='select') EQUALS 'b690fa1a-7b3d-4181-95d8-f5c75927c3fc' (name='medium')"
        )

    def test_get_restriction_text__caninput(self):
        attribute_id = "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
        condition = {"enable": False, "_type": "CanInput"}
        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert actual == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') CAN NOT INPUT"

    def test_get_restriction_text__haslabel(self):
        attribute_id = "15235360-4f46-42ac-927d-0e046bf52ddd"
        condition = {
            "labels": ["40f7796b-3722-4eed-9c0c-04a27f9165d2", "22b5189b-af7b-4d9c-83a5-b92f122170ec"],
            "_type": "HasLabel",
        }

        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert (
            actual
            == "'link' (id='15235360-4f46-42ac-927d-0e046bf52ddd', type='link') HAS LABEL 'bike' (id='40f7796b-3722-4eed-9c0c-04a27f9165d2'), 'bus' (id='22b5189b-af7b-4d9c-83a5-b92f122170ec')"  # noqa: E501
        )

    def test_get_restriction_text__imply(self):
        attribute_id = "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
        condition = {
            "premise": {
                "additional_data_definition_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
                "condition": {"value": "true", "_type": "Equals"},
            },
            "condition": {"value": "[0-9]", "_type": "Matches"},
            "_type": "Imply",
        }

        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert (
            actual
            == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') MATCHES '[0-9]' IF 'unclear' (id='f12a0b59-dfce-4241-bb87-4b2c0259fc6f', type='flag') EQUALS 'true'"  # noqa: E501
        )

    def test_get_restriction_text__equals_not_exist_attribute(self):
        attribute_id = "not-exist"
        condition = {"value": "foo", "_type": "Equals"}

        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert actual == "'' (id='not-exist') EQUALS 'foo'"

    def test_get_restriction_text__dropdown_not_exist_attribute(self):
        attribute_id = "71620647-98cf-48ad-b43b-4af425a24f32"
        condition = {"value": "", "_type": "Equals"}

        actual = self.obj.get_restriction_text(attribute_id, condition)
        assert actual == "'type' (id='71620647-98cf-48ad-b43b-4af425a24f32', type='select') EQUALS ''"

    def test_get_restriction_text_list(self):
        actual1 = self.obj.get_restriction_text_list(self.annotation_specs["restrictions"], target_attribute_names=["link"])
        assert len(actual1) == 1

        actual2 = self.obj.get_restriction_text_list(self.annotation_specs["restrictions"], target_label_names=["car"])
        assert len(actual2) == 9
