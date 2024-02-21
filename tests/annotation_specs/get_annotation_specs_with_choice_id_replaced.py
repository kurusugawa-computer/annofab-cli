import copy

from annofabcli.annotation_specs.get_annotation_specs_with_choice_id_replaced import ReplacingChoiceId


class TestReplacingChoiceId:
    attribute_list = [  # noqa: RUF012
        {
            "additional_data_definition_id": "f98a9545-5864-4e5b-a945-d327001a0179",
            "name": {
                "messages": [{"lang": "ja-JP", "message": "向き"}, {"lang": "en-US", "message": "direction"}],
                "default_lang": "ja-JP",
            },
            "type": "select",
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
        assert attribtue["choices"][0]["choice_id"] == "front"  # type: ignore[index]
        assert attribtue["choices"][1]["choice_id"] == "rear"  # type: ignore[index]
