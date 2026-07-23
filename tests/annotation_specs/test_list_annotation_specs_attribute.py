from __future__ import annotations

import json
from pathlib import Path

from annofabcli.annotation_specs.list_annotation_specs_attribute import create_flatten_attribute_list_from_additionals

DATA_DIR = Path("./tests/data/annotation_specs")


def test_create_flatten_attribute_list_from_additionalsは参照ラベル情報を出力する() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    actual = create_flatten_attribute_list_from_additionals(
        annotation_specs["additionals"],
        annotation_specs["labels"],
        annotation_specs["restrictions"],
    )

    comment_attribute = next(e for e in actual if e.attribute_id == "54fa5e97-6f88-49a4-aeb0-a91a15d11528")
    assert comment_attribute.reference_label_count == 1
    assert comment_attribute.label_ids == ["car_label_id"]
    assert comment_attribute.label_name_ens == ["car"]


def test_create_flatten_attribute_list_from_additionalsは未参照属性のラベル情報を空配列にする() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    annotation_specs["additionals"].append(
        {
            "additional_data_definition_id": "unreferenced_attribute_id",
            "read_only": False,
            "name": {
                "messages": [{"lang": "en-US", "message": "unreferenced"}],
                "default_lang": "en-US",
            },
            "keybind": [],
            "type": "comment",
            "default": "",
            "choices": [],
            "metadata": {},
        }
    )

    actual = create_flatten_attribute_list_from_additionals(
        annotation_specs["additionals"],
        annotation_specs["labels"],
        annotation_specs["restrictions"],
    )

    unreferenced_attribute = next(e for e in actual if e.attribute_id == "unreferenced_attribute_id")
    assert unreferenced_attribute.reference_label_count == 0
    assert unreferenced_attribute.label_ids == []
    assert unreferenced_attribute.label_name_ens == []
