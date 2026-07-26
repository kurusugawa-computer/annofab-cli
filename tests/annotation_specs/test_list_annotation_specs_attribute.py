from __future__ import annotations

import json
from pathlib import Path

from annofabcli.annotation_specs.list_annotation_specs_attribute import create_attribute_dict_list_for_json, create_flatten_attribute_list_from_additionals

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
    assert comment_attribute.keybind is None
    assert comment_attribute.keybind_text is None


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


def test_create_attribute_dict_list_for_jsonは選択肢情報を出力する() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    actual = create_attribute_dict_list_for_json(
        annotation_specs["additionals"],
        annotation_specs["labels"],
        annotation_specs["restrictions"],
    )

    type_attribute = next(e for e in actual if e["attribute_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
    assert type_attribute["choice_count"] == 3
    assert type_attribute["choices"] == [
        {
            "choice_id": "08ec927c-18e6-4bba-837a-b16de7061580",
            "choice_name_en": "large",
            "choice_name_ja": "large",
            "choice_name_vi": None,
            "is_default": False,
            "keybind": None,
            "keybind_text": None,
        },
        {
            "choice_id": "b690fa1a-7b3d-4181-95d8-f5c75927c3fc",
            "choice_name_en": "medium",
            "choice_name_ja": "medium",
            "choice_name_vi": None,
            "is_default": False,
            "keybind": None,
            "keybind_text": None,
        },
        {
            "choice_id": "74691a87-7962-4fa9-ba52-7cc466ecd982",
            "choice_name_en": "small",
            "choice_name_ja": "small",
            "choice_name_vi": None,
            "is_default": False,
            "keybind": None,
            "keybind_text": None,
        },
    ]


def test_create_attribute_dict_list_for_jsonは選択肢がない属性では空配列を出力する() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    actual = create_attribute_dict_list_for_json(
        annotation_specs["additionals"],
        annotation_specs["labels"],
        annotation_specs["restrictions"],
    )

    comment_attribute = next(e for e in actual if e["attribute_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528")
    assert comment_attribute["choice_count"] == 0
    assert comment_attribute["choices"] == []
