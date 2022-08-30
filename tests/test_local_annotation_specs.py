import copy
import json
import os
from pathlib import Path

from annofabcli.annotation_specs.get_annotation_specs_with_attribute_id_replaced import ReplacingAttributeId
from annofabcli.annotation_specs.get_annotation_specs_with_choice_id_replaced import ReplacingChoiceId
from annofabcli.annotation_specs.get_annotation_specs_with_label_id_replaced import ReplacingLabelId
from annofabcli.annotation_specs.list_attribute_restriction import ListAttributeRestrictionMain

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/annotation_specs")
out_dir = Path("./tests/out/annotation_specs")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")


class TestListAttributeRestrictionMain:
    @classmethod
    def setup_class(cls):
        with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
            annotation_specs = json.load(f)

        cls.obj = ListAttributeRestrictionMain(
            labels=annotation_specs["labels"], additionals=annotation_specs["additionals"]
        )
        cls.annotation_specs = annotation_specs

    def test_get_restriction_text__equals(self):
        restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "foo", "_type": "Equals"},
        }
        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert actual == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') EQUALS 'foo'"

    def test_get_restriction_text__equals_dropdown(self):
        restriction = {
            "additional_data_definition_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "condition": {"value": "b690fa1a-7b3d-4181-95d8-f5c75927c3fc", "_type": "Equals"},
        }
        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert (
            actual
            == "'type' (id='71620647-98cf-48ad-b43b-4af425a24f32', type='select') EQUALS 'b690fa1a-7b3d-4181-95d8-f5c75927c3fc'(name='medium')"
        )

    def test_get_restriction_text__caninput(self):
        restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"enable": False, "_type": "CanInput"},
        }

        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert actual == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') CAN NOT INPUT"

    def test_get_restriction_text__haslabel(self):
        restriction = {
            "additional_data_definition_id": "15235360-4f46-42ac-927d-0e046bf52ddd",
            "condition": {
                "labels": ["40f7796b-3722-4eed-9c0c-04a27f9165d2", "22b5189b-af7b-4d9c-83a5-b92f122170ec"],
                "_type": "HasLabel",
            },
        }

        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert (
            actual
            == "'link' (id='15235360-4f46-42ac-927d-0e046bf52ddd', type='link') HAS LABEL 'bike' (id='40f7796b-3722-4eed-9c0c-04a27f9165d2'), 'bus' (id='22b5189b-af7b-4d9c-83a5-b92f122170ec')"
        )

    def test_get_restriction_text__imply(self):
        restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {
                "premise": {
                    "additional_data_definition_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
                    "condition": {"value": "true", "_type": "Equals"},
                },
                "condition": {"value": "[0-9]", "_type": "Matches"},
                "_type": "Imply",
            },
        }

        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert (
            actual
            == "'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') MATCHES '[0-9]' IF 'unclear' (id='f12a0b59-dfce-4241-bb87-4b2c0259fc6f', type='flag') EQUALS 'true'"
        )

    def test_get_restriction_text__equals_not_exist_attribute(self):
        restriction = {
            "additional_data_definition_id": "not-exist",
            "condition": {"value": "foo", "_type": "Equals"},
        }
        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert actual == "'' (id='not-exist') EQUALS 'foo'"

    def test_get_restriction_text__dropdown_not_exist_attribute(self):
        restriction = {
            "additional_data_definition_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "condition": {"value": "", "_type": "Equals"},
        }
        actual = self.obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
        assert actual == "'type' (id='71620647-98cf-48ad-b43b-4af425a24f32', type='select') EQUALS ''"

    def test_get_restriction_text_list(self):
        actual1 = self.obj.get_restriction_text_list(
            self.annotation_specs["restrictions"], target_attribute_names=["link"]
        )
        assert len(actual1) == 1

        actual2 = self.obj.get_restriction_text_list(self.annotation_specs["restrictions"], target_label_names=["car"])
        assert len(actual2) == 9


class TestReplacingLabelId:
    label_list = [
        {
            "label_id": "id1",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "name_ja1"}, {"lang": "en-US", "message": "name_en1"}],
                "default_lang": "ja-JP",
            },
        }
    ]
    restriction_list = [
        {
            "additional_data_definition_id": "attr1",
            "condition": {
                "_type": "Imply",
                "premise": {
                    "additional_data_definition_id": "attr2",
                    "condition": {"_type": "Equals", "value": "true"},
                },
                "condition": {"_type": "HasLabel", "labels": ["id1", "id2"]},
            },
        }
    ]

    def test_replace_label_id_of_restrictions(self):

        restriction_list = copy.deepcopy(self.restriction_list)
        ReplacingLabelId().replace_label_id_of_restrictions("id1", "new_label1", restriction_list)
        assert restriction_list[0]["condition"]["condition"]["labels"][0] == "new_label1"

    def test_main(self):
        annotation_specs = {
            "labels": copy.deepcopy(self.label_list),
            "restrictions": copy.deepcopy(self.restriction_list),
        }
        ReplacingLabelId(all_yes=True).main(annotation_specs)
        assert annotation_specs["labels"][0]["label_id"] == "name_en1"
        assert annotation_specs["restrictions"][0]["condition"]["condition"]["labels"][0] == "name_en1"


class TestReplacingAttributeId:
    attribute_list = [
        {
            "additional_data_definition_id": "attr1",
            "name": {
                "messages": [{"lang": "ja-JP", "message": "属性1"}, {"lang": "en-US", "message": "new_attr1"}],
                "default_lang": "ja-JP",
            },
            "choices": [
                {
                    "choice_id": "aaa",
                    "name": {
                        "messages": [{"lang": "ja-JP", "message": "真正面"}, {"lang": "en-US", "message": "rear"}],
                        "default_lang": "ja-JP",
                    },
                    "keybind": [],
                },
                {
                    "choice_id": "a5ebf59b-0484-446d-ac11-14a4736026e4",
                    "name": {
                        "messages": [{"lang": "ja-JP", "message": "真後ろ"}, {"lang": "en-US", "message": "rear"}],
                        "default_lang": "ja-JP",
                    },
                    "keybind": [],
                },
            ],
        }
    ]
    label_list = [
        {
            "label_id": "id1",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "name_ja1"}, {"lang": "en-US", "message": "name_en1"}],
                "default_lang": "ja-JP",
            },
            "additional_data_definitions": ["attr1", "attr2"],
        }
    ]
    restriction_list = [
        {
            "additional_data_definition_id": "attr1",
            "condition": {
                "_type": "Imply",
                "premise": {
                    "additional_data_definition_id": "attr2",
                    "condition": {"_type": "Equals", "value": "true"},
                },
                "condition": {"_type": "HasLabel", "labels": ["id1", "id2"]},
            },
        }
    ]

    def test_replace_attribute_id_of_restrictions(self):

        restriction_list = copy.deepcopy(self.restriction_list)
        ReplacingAttributeId().replace_attribute_id_of_restrictions("attr1", "new_attr1", restriction_list)
        restriction = restriction_list[0]
        assert restriction["additional_data_definition_id"] == "new_attr1"
        # 変わっていないことの確認
        assert restriction["condition"]["premise"]["additional_data_definition_id"] == "attr2"

    def test_replace_attribute_id_of_labels(self):

        label_list = copy.deepcopy(self.label_list)
        ReplacingAttributeId().replace_attribute_id_of_labels("attr1", "new_attr1", label_list)
        label = label_list[0]
        assert label["additional_data_definitions"] == ["new_attr1", "attr2"]

    def test_main(self):
        annotation_specs = {
            "labels": copy.deepcopy(self.label_list),
            "additionals": copy.deepcopy(self.attribute_list),
            "restrictions": copy.deepcopy(self.restriction_list),
        }
        ReplacingAttributeId(all_yes=True).main(annotation_specs)
        assert annotation_specs["additionals"][0]["additional_data_definition_id"] == "new_attr1"
        assert annotation_specs["labels"][0]["additional_data_definitions"] == ["new_attr1", "attr2"]
        assert annotation_specs["restrictions"][0]["additional_data_definition_id"] == "new_attr1"


class TestReplacingChoiceId:
    attribute_list = [
        {
            "additional_data_definition_id": "f98a9545-5864-4e5b-a945-d327001a0179",
            "name": {
                "messages": [{"lang": "ja-JP", "message": "向き"}, {"lang": "en-US", "message": "direction"}],
                "default_lang": "ja-JP",
            },
            "type":"select",
            "default": "3475515f-ba44-4a8d-b32b-72635e420048",
            "choices": [
                {
                    "choice_id": "3475515f-ba44-4a8d-b32b-72635e420048",
                    "name": {
                        "messages": [{"lang": "ja-JP", "message": "前"}, {"lang": "en-US", "message": "front"}],
                        "default_lang": "ja-JP",
                    },
                },
                {
                    "choice_id": "a5ebf59b-0484-446d-ac11-14a4736026e4",
                    "name": {
                        "messages": [{"lang": "ja-JP", "message": "後ろ"}, {"lang": "en-US", "message": "rear"}],
                        "default_lang": "ja-JP",
                    },
                },
            ],
        }
    ]

    def test_main(self):
        annotation_specs = {
            "additionals": copy.deepcopy(self.attribute_list),
        }
        ReplacingChoiceId(all_yes=True).main(annotation_specs)
        attribtue = annotation_specs["additionals"][0]
        assert attribtue["default"] == "front"
        assert attribtue["choices"][0]["choice_id"] == "front"
        assert attribtue["choices"][1]["choice_id"] == "rear"
