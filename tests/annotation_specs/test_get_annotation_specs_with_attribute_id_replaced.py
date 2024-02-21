import copy

from annofabcli.annotation_specs.get_annotation_specs_with_attribute_id_replaced import ReplacingAttributeId


class TestReplacingAttributeId:
    attribute_list = [  # noqa: RUF012
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
    label_list = [  # noqa: RUF012
        {
            "label_id": "id1",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "name_ja1"}, {"lang": "en-US", "message": "name_en1"}],
                "default_lang": "ja-JP",
            },
            "additional_data_definitions": ["attr1", "attr2"],
        }
    ]
    restriction_list = [  # noqa: RUF012
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
        assert restriction["condition"]["premise"]["additional_data_definition_id"] == "attr2"  # type: ignore[index]

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
        assert annotation_specs["additionals"][0]["additional_data_definition_id"] == "new_attr1"  # type: ignore[index]
        assert annotation_specs["labels"][0]["additional_data_definitions"] == ["new_attr1", "attr2"]  # type: ignore[index]
        assert annotation_specs["restrictions"][0]["additional_data_definition_id"] == "new_attr1"  # type: ignore[index]
