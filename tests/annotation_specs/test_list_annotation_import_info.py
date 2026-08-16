from __future__ import annotations

import json
from pathlib import Path

from annofabcli.annotation_specs.list_annotation_import_info import create_annotation_import_info_list

DATA_DIR = Path("./tests/data/annotation_specs")


def test_create_annotation_import_info_listはimportに必要な情報を出力する() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["additionals"][0]["read_only"] = True

    actual = create_annotation_import_info_list(annotation_specs)

    car_label = next(e for e in actual if e.label_name_en == "car")
    assert car_label.label_name_ja == "car"
    assert car_label.annotation_type == "bounding_box"
    assert [e.attribute_name_en for e in car_label.attributes] == ["comment", "link", "type", "unclear"]
    assert [e.attribute_name_ja for e in car_label.attributes] == ["comment", "link", "type", "unclear"]
    assert [e.read_only for e in car_label.attributes] == [True, False, False, False]

    type_attribute = next(e for e in car_label.attributes if e.attribute_name_en == "type")
    assert type_attribute.attribute_type == "select"
    assert [e.choice_name_en for e in type_attribute.choices] == ["large", "medium", "small"]
    assert [e.choice_name_ja for e in type_attribute.choices] == ["large", "medium", "small"]


def test_create_annotation_import_info_listは属性がないラベルも出力する() -> None:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)

    actual = create_annotation_import_info_list(annotation_specs)

    bike_label = next(e for e in actual if e.label_name_en == "bike")
    assert bike_label.label_name_ja == "bike"
    assert bike_label.annotation_type == "bounding_box"
    assert bike_label.attributes == []
