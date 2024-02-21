from __future__ import annotations

import copy

from annofabcli.annotation_specs.get_annotation_specs_with_label_id_replaced import ReplacingLabelId


class TestReplacingLabelId:
    label_list = [  # noqa: RUF012
        {
            "label_id": "id1",
            "label_name": {
                "messages": [{"lang": "ja-JP", "message": "name_ja1"}, {"lang": "en-US", "message": "name_en1"}],
                "default_lang": "ja-JP",
            },
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

    def test_replace_label_id_of_restrictions(self):
        restriction_list = copy.deepcopy(self.restriction_list)
        ReplacingLabelId().replace_label_id_of_restrictions("id1", "new_label1", restriction_list)
        labels: list[str] = restriction_list[0]["condition"]["condition"]["labels"]  # type: ignore[index]
        assert labels[0] == "new_label1"

    def test_main(self):
        annotation_specs = {
            "labels": copy.deepcopy(self.label_list),
            "restrictions": copy.deepcopy(self.restriction_list),
        }
        ReplacingLabelId(all_yes=True).main(annotation_specs)
        assert annotation_specs["labels"][0]["label_id"] == "name_en1"
        assert annotation_specs["restrictions"][0]["condition"]["condition"]["labels"][0] == "name_en1"  # type: ignore[index]
