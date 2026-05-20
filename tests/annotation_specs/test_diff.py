from __future__ import annotations

import argparse
import copy
import json
from typing import cast

import annofabapi
import pytest
import yaml

from annofabcli.__main__ import main
from annofabcli.annotation_specs.diff_annotation_specs import AnnotationSpecsDiffCommand
from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.diff_text_formatter import format_annotation_specs_diff_as_text
from annofabcli.common.facade import AnnofabApiFacade


def _create_choice(choice_id: str, *, ja: str, en: str, vi: str) -> dict:
    return {
        "choice_id": choice_id,
        "name": {
            "messages": [
                {"lang": "ja-JP", "message": ja},
                {"lang": "en-US", "message": en},
                {"lang": "vi-VN", "message": vi},
            ],
            "default_lang": "ja-JP",
        },
        "keybind": [],
    }


def _create_attribute(attribute_id: str, *, ja: str, en: str, vi: str, default: str | bool, choices: list[dict]) -> dict:
    return {
        "additional_data_definition_id": attribute_id,
        "read_only": False,
        "name": {
            "messages": [
                {"lang": "ja-JP", "message": ja},
                {"lang": "en-US", "message": en},
                {"lang": "vi-VN", "message": vi},
            ],
            "default_lang": "ja-JP",
        },
        "keybind": [],
        "type": "select" if len(choices) > 0 else "flag",
        "default": default,
        "choices": choices,
        "metadata": {},
    }


def _create_label(label_id: str, *, ja: str, en: str, vi: str, color: dict[str, int], additional_data_definitions: list[str]) -> dict:
    return {
        "label_id": label_id,
        "label_name": {
            "messages": [
                {"lang": "ja-JP", "message": ja},
                {"lang": "en-US", "message": en},
                {"lang": "vi-VN", "message": vi},
            ],
            "default_lang": "ja-JP",
        },
        "keybind": [],
        "annotation_type": "bounding_box",
        "additional_data_definitions": additional_data_definitions,
        "color": color,
        "field_values": {},
        "metadata": {},
    }


def _create_restriction(attribute_id: str, condition: dict) -> dict:
    return {
        "additional_data_definition_id": attribute_id,
        "condition": condition,
    }


def _create_inspection_phrase(phrase_id: str, *, ja: str, en: str, vi: str, description: str = "") -> dict:
    return {
        "id": phrase_id,
        "text": {
            "messages": [
                {"lang": "ja-JP", "message": ja},
                {"lang": "en-US", "message": en},
                {"lang": "vi-VN", "message": vi},
            ],
            "default_lang": "ja-JP",
        },
        "description": description,
    }


def _create_annotation_specs() -> dict:
    return {
        "format_version": 3,
        "labels": [
            _create_label(
                "label_car",
                ja="車",
                en="car",
                vi="xe",
                color={"red": 255, "green": 0, "blue": 0},
                additional_data_definitions=["attr_occluded", "attr_truncated"],
            )
        ],
        "additionals": [
            _create_attribute(
                "attr_occluded",
                ja="遮蔽",
                en="occluded",
                vi="bị che",
                default="choice_yes",
                choices=[
                    _create_choice("choice_yes", ja="はい", en="yes", vi="co"),
                    _create_choice("choice_no", ja="いいえ", en="no", vi="khong"),
                ],
            ),
            _create_attribute(
                "attr_truncated",
                ja="切れ",
                en="truncated",
                vi="cat",
                default=False,
                choices=[],
            ),
        ],
        "restrictions": [],
        "inspection_phrases": [
            _create_inspection_phrase("phrase_blur", ja="ぼやけています", en="blurred", vi="mo"),
            _create_inspection_phrase("phrase_occluded", ja="隠れています", en="occluded", vi="bi che"),
        ],
        "metadata": {},
    }


class TestCreateAnnotationSpecsDiff:
    def test_ラベルと属性の差分を生成できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)

        right_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}
        right_specs["labels"][0]["label_name"]["messages"][0]["message"] = "自動車"
        right_specs["labels"][0]["additional_data_definitions"] = ["attr_pose", "attr_occluded"]
        right_specs["additionals"] = [
            _create_attribute(
                "attr_pose",
                ja="姿勢",
                en="pose",
                vi="tu the",
                default=False,
                choices=[],
            ),
            _create_attribute(
                "attr_occluded",
                ja="隠れ",
                en="occluded",
                vi="bị che",
                default="choice_no",
                choices=[
                    _create_choice("choice_unknown", ja="不明", en="unknown", vi="khong ro"),
                    _create_choice("choice_yes", ja="はい", en="yes", vi="co-moi"),
                    _create_choice("choice_no", ja="いいえ", en="no", vi="khong"),
                ],
            ),
        ]

        actual = create_annotation_specs_diff(left_specs, right_specs)
        actual_dict = actual.model_dump(exclude_none=True)

        assert actual_dict["labels"]["added_label_ids"] == []
        assert actual_dict["labels"]["removed_label_ids"] == []
        assert actual_dict["labels"]["changed_labels"] == [
            {
                "label_id": "label_car",
                "color_changed": True,
                "keybind_changed": False,
                "label_name_ja_changed": True,
                "label_name_en_changed": False,
                "label_name_vi_changed": False,
                "attributes_order_changed": False,
                "added_attribute_ids": ["attr_pose"],
                "removed_attribute_ids": ["attr_truncated"],
                "field_values_changed": False,
                "metadata_changed": False,
                "annotation_type_changed": False,
            }
        ]
        assert actual_dict["attributes"] == {
            "added_attribute_ids": ["attr_pose"],
            "removed_attribute_ids": ["attr_truncated"],
            "changed_attributes": [
                {
                    "attribute_id": "attr_occluded",
                    "read_only_changed": False,
                    "attribute_name_ja_changed": True,
                    "attribute_name_en_changed": False,
                    "attribute_name_vi_changed": False,
                    "keybind_changed": False,
                    "type_changed": False,
                    "default_changed": True,
                    "metadata_changed": False,
                    "choices_order_changed": False,
                    "added_choice_ids": ["choice_unknown"],
                    "removed_choice_ids": [],
                    "changed_choices": [
                        {
                            "choice_id": "choice_yes",
                            "choice_name_ja_changed": False,
                            "choice_name_en_changed": False,
                            "choice_name_vi_changed": True,
                            "keybind_changed": False,
                        }
                    ],
                }
            ],
        }

    def test_targetでlabelsのみ指定できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}

        actual = create_annotation_specs_diff(left_specs, right_specs, targets={"labels"})

        assert actual.labels is not None
        assert actual.attributes is None
        assert actual.inspection_phrases is None
        assert actual.metadata is None

    def test_属性制約の差分を生成できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        left_specs["restrictions"] = [
            _create_restriction("attr_occluded", {"_type": "Equals", "value": "choice_yes"}),
            _create_restriction("attr_truncated", {"_type": "CanInput", "enable": False}),
            _create_restriction("attr_truncated", {"_type": "HasLabel", "labels": ["label_car", "label_bus"]}),
        ]
        right_specs["restrictions"] = [
            _create_restriction("attr_occluded", {"_type": "Equals", "value": "choice_yes"}),
            _create_restriction("attr_occluded", {"_type": "NotEquals", "value": "choice_no"}),
            _create_restriction("attr_truncated", {"_type": "CanInput", "enable": True}),
            _create_restriction("attr_truncated", {"_type": "HasLabel", "labels": ["label_bus", "label_car"]}),
        ]

        actual = create_annotation_specs_diff(left_specs, right_specs)
        actual_dict = actual.model_dump(exclude_none=True)

        assert actual_dict["attribute_restrictions"] == {
            "changed_attribute_restrictions": [
                {
                    "attribute_id": "attr_occluded",
                    "added_restrictions": [
                        {
                            "condition": {"_type": "NotEquals", "value": "choice_no"},
                        }
                    ],
                    "removed_restrictions": [],
                },
                {
                    "attribute_id": "attr_truncated",
                    "added_restrictions": [
                        {
                            "condition": {"_type": "CanInput", "enable": True},
                        }
                    ],
                    "removed_restrictions": [
                        {
                            "condition": {"_type": "CanInput", "enable": False},
                        }
                    ],
                },
            ]
        }

    def test_定型指摘の追加削除をID単位で差分にできる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"] = [
            _create_inspection_phrase("phrase_occluded", ja="隠れています", en="occluded", vi="bi che"),
            _create_inspection_phrase("phrase_too_dark", ja="暗すぎます", en="too dark", vi="qua toi"),
        ]

        actual = create_annotation_specs_diff(left_specs, right_specs)
        actual_dict = actual.model_dump(exclude_none=True)

        assert actual_dict["inspection_phrases"] == {
            "added_inspection_phrase_ids": ["phrase_too_dark"],
            "removed_inspection_phrase_ids": ["phrase_blur"],
            "changed_inspection_phrases": [],
        }

    def test_定型指摘の名前変更だけを差分にできる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"][0]["text"]["messages"][0]["message"] = "ぼやけています2"
        right_specs["inspection_phrases"][0]["text"]["messages"][1]["message"] = "blurred2"
        right_specs["inspection_phrases"][0]["text"]["messages"][2]["message"] = "mo2"
        right_specs["inspection_phrases"][1]["description"] = "説明は差分対象外"

        actual = create_annotation_specs_diff(left_specs, right_specs, targets={"inspection_phrases"})
        actual_dict = actual.model_dump(exclude_none=True)

        assert actual_dict["inspection_phrases"] == {
            "added_inspection_phrase_ids": [],
            "removed_inspection_phrase_ids": [],
            "changed_inspection_phrases": [
                {
                    "inspection_phrase_id": "phrase_blur",
                    "inspection_phrase_name_ja_changed": True,
                    "inspection_phrase_name_en_changed": True,
                    "inspection_phrase_name_vi_changed": True,
                }
            ],
        }

    def test_定型指摘の順序変更は差分にしない(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"] = list(reversed(right_specs["inspection_phrases"]))

        actual = create_annotation_specs_diff(left_specs, right_specs, targets={"inspection_phrases"})

        assert actual.has_changes() is False

    def test_metadataの差分をキー単位で生成できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        left_specs["metadata"] = {
            "removed_key": "削除",
            "changed_key": {"version": 1},
            "unchanged_key": True,
        }
        right_specs["metadata"] = {
            "changed_key": {"version": 2},
            "unchanged_key": True,
            "added_key": ["追加"],
        }

        actual = create_annotation_specs_diff(left_specs, right_specs, targets={"metadata"})
        actual_dict = actual.model_dump(exclude_none=True)

        assert actual_dict["metadata"] == {
            "added_metadata_keys": ["added_key"],
            "removed_metadata_keys": ["removed_key"],
            "changed_metadata_keys": ["changed_key"],
        }


class TestFormatAnnotationSpecsDiffAsText:
    def test_差分がないときは空文字を返す(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )

        assert actual == ""

    def test_textでidではなく英語名を出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["additional_data_definitions"] = ["attr_pose", "attr_occluded"]
        right_specs["additionals"] = [
            _create_attribute(
                "attr_pose",
                ja="姿勢",
                en="pose",
                vi="tu the",
                default=False,
                choices=[],
            ),
            _create_attribute(
                "attr_occluded",
                ja="隠れ",
                en="occluded",
                vi="bị che",
                default="choice_yes",
                choices=[
                    _create_choice("choice_unknown", ja="不明", en="unknown", vi="khong ro"),
                    _create_choice("choice_yes", ja="はい", en="yes", vi="co"),
                    _create_choice("choice_no", ja="いいえ", en="no", vi="khong"),
                ],
            ),
        ]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )
        actual_yaml = yaml.safe_load(actual.split("[labels]\n", 1)[1].split("\n\n[attributes]", 1)[0])

        assert "label_id:" not in actual
        assert "attribute_id:" not in actual
        assert "choice_id:" not in actual
        assert actual_yaml["changed"][0]["label_name_en"] == "car"
        assert actual_yaml["changed"][0]["added_attributes"] == ["pose"]
        assert actual_yaml["changed"][0]["removed_attributes"] == ["truncated"]

    def test_detail_textで変更前後の値を出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}
        right_specs["labels"][0]["keybind"] = [{"ctrl": True, "alt": False, "shift": False, "code": "Digit1"}]
        right_specs["labels"][0]["label_name"]["messages"][0]["message"] = "自動車"
        right_specs["additionals"][0]["name"]["messages"][2]["message"] = "co-moi"

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=True)
        labels_yaml = yaml.safe_load(actual.split("[labels]\n", 1)[1].split("\n\n[attributes]", 1)[0])
        attributes_yaml = yaml.safe_load(actual.split("[attributes]\n", 1)[1])

        assert "[labels]" in actual
        assert labels_yaml["changed"][0]["changes"]["color"] == {"left": "#FF0000", "right": "#00FF00"}
        assert labels_yaml["changed"][0]["changes"]["keybind"] == {"left": "", "right": "Ctrl+Digit1"}
        assert labels_yaml["changed"][0]["changes"]["label_name_ja"] == {"left": "車", "right": "自動車"}
        assert "[attributes]" in actual
        assert attributes_yaml["changed"][0]["changes"]["attribute_name_vi"] == {"left": "bị che", "right": "co-moi"}
        assert "attribute_id:" not in actual
        assert "choice_id:" not in actual

    def test_detail_textのラベル差分はchanged_field_namesと同じ順序で出力する(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["label_name"]["messages"][1]["message"] = "car-updated"
        right_specs["labels"][0]["label_name"]["messages"][0]["message"] = "自動車"
        right_specs["labels"][0]["label_name"]["messages"][2]["message"] = "xe-moi"
        right_specs["labels"][0]["annotation_type"] = "polygon"
        right_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}
        right_specs["labels"][0]["keybind"] = [{"ctrl": True, "alt": False, "shift": False, "code": "Digit3"}]
        right_specs["labels"][0]["additional_data_definitions"] = ["attr_truncated", "attr_occluded"]
        right_specs["labels"][0]["field_values"] = {"score": 1}
        right_specs["labels"][0]["metadata"] = {"updated": True}

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        labels_yaml = yaml.safe_load(actual.split("[labels]\n", 1)[1])

        expected_keys = [
            "label_name_en:",
            "label_name_ja:",
            "label_name_vi:",
            "annotation_type:",
            "color:",
            "keybind:",
            "attributes:",
            "attributes_order:",
            "field_values:",
            "metadata:",
        ]
        assert [f"{key}:" for key in labels_yaml["changed"][0]["changes"].keys()] == expected_keys
        assert labels_yaml["changed"][0]["label_name_en"] == "car-updated"
        assert labels_yaml["changed"][0]["changes"]["label_name_en"] == {"left": "car", "right": "car-updated"}

    def test_detail_textの属性差分はchanged_field_namesと同じ順序で出力する(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["additionals"][0]["name"]["messages"][1]["message"] = "occluded-updated"
        right_specs["additionals"][0]["name"]["messages"][0]["message"] = "遮蔽更新"
        right_specs["additionals"][0]["name"]["messages"][2]["message"] = "bi-che-moi"
        right_specs["additionals"][0]["type"] = "text"
        right_specs["additionals"][0]["keybind"] = [{"ctrl": True, "alt": False, "shift": False, "code": "Digit2"}]
        right_specs["additionals"][0]["default"] = "choice_no"
        right_specs["additionals"][0]["read_only"] = True
        right_specs["additionals"][0]["choices"] = list(reversed(right_specs["additionals"][0]["choices"]))
        right_specs["additionals"][0]["metadata"] = {"updated": True}

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        attributes_yaml = yaml.safe_load(actual.split("[attributes]\n", 1)[1])

        expected_keys = [
            "attribute_name_en:",
            "attribute_name_ja:",
            "attribute_name_vi:",
            "type:",
            "keybind:",
            "default:",
            "read_only:",
            "choices:",
            "choices_order:",
            "metadata:",
        ]
        assert [f"{key}:" for key in attributes_yaml["changed"][0]["changes"].keys()] == expected_keys
        assert attributes_yaml["changed"][0]["attribute_name_en"] == "occluded-updated"
        assert attributes_yaml["changed"][0]["changes"]["attribute_name_en"] == {"left": "occluded", "right": "occluded-updated"}

    def test_detail_textで選択肢や属性も英語名を出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["additional_data_definitions"] = ["attr_pose", "attr_occluded"]
        right_specs["additionals"] = [
            _create_attribute(
                "attr_pose",
                ja="姿勢",
                en="pose",
                vi="tu the",
                default=False,
                choices=[],
            ),
            _create_attribute(
                "attr_occluded",
                ja="遮蔽",
                en="occluded",
                vi="bị che",
                default="choice_yes",
                choices=[
                    _create_choice("choice_unknown", ja="不明", en="unknown", vi="khong ro"),
                    _create_choice("choice_yes", ja="はい", en="yes_changed", vi="co"),
                    _create_choice("choice_no", ja="いいえ", en="no", vi="khong"),
                ],
            ),
        ]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        labels_yaml = yaml.safe_load(actual.split("[labels]\n", 1)[1].split("\n\n[attributes]", 1)[0])
        attributes_yaml = yaml.safe_load(actual.split("[attributes]\n", 1)[1])

        assert attributes_yaml["changed"][0]["attribute_name_en"] == "occluded"
        assert labels_yaml["changed"][0]["changes"]["attributes"] == {"left": '["occluded", "truncated"]', "right": '["pose", "occluded"]'}
        assert labels_yaml["changed"][0]["added_attributes"] == ["pose"]
        assert labels_yaml["changed"][0]["removed_attributes"] == ["truncated"]
        assert attributes_yaml["changed"][0]["changes"]["choices"] == {"left": '["yes", "no"]', "right": '["unknown", "yes_changed", "no"]'}
        assert attributes_yaml["changed"][0]["added_choices"] == ["unknown"]
        assert attributes_yaml["changed"][0]["changed_choices"][0]["choice_name_en"] == "yes_changed"

    def test_detail_textの選択肢差分はchanged_field_namesと同じ順序で出力する(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_choice = right_specs["additionals"][0]["choices"][0]
        right_choice["name"]["messages"][1]["message"] = "yes-updated"
        right_choice["name"]["messages"][0]["message"] = "はい更新"
        right_choice["name"]["messages"][2]["message"] = "co-moi"
        right_choice["keybind"] = [{"ctrl": True, "alt": False, "shift": False, "code": "Digit4"}]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        attributes_yaml = yaml.safe_load(actual.split("[attributes]\n", 1)[1])

        expected_keys = [
            "choice_name_en:",
            "choice_name_ja:",
            "choice_name_vi:",
            "keybind:",
        ]
        assert attributes_yaml["changed"][0]["attribute_name_en"] == "occluded"
        assert attributes_yaml["changed"][0]["changed_choices"][0]["choice_name_en"] == "yes-updated"
        assert [f"{key}:" for key in attributes_yaml["changed"][0]["changed_choices"][0]["changes"].keys()] == expected_keys
        assert attributes_yaml["changed"][0]["changed_choices"][0]["changes"]["choice_name_en"] == {"left": "yes", "right": "yes-updated"}

    def test_attribute_restrictionをtextで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["restrictions"] = [
            _create_restriction("attr_occluded", {"_type": "Equals", "value": "choice_yes"}),
        ]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )
        actual_yaml = yaml.safe_load(actual.split("[attribute_restrictions]\n", 1)[1])

        assert "[attribute_restrictions]" in actual
        assert actual_yaml["changed"][0]["attribute_name_en"] == "occluded"
        assert actual_yaml["changed"][0]["added_restrictions"] == ["'occluded' is 'yes'"]
        assert "attr_occluded" not in actual

    def test_変更があるセクションだけを出力する(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["additionals"][0]["default"] = "choice_no"

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )

        assert "[attributes]" in actual
        assert "[labels]" not in actual
        assert "[attribute_restrictions]" not in actual
        assert "差分はありません。" not in actual

    def test_attribute_restrictionをdetail_textで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["restrictions"] = [
            _create_restriction("attr_truncated", {"_type": "CanInput", "enable": False}),
        ]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        actual_yaml = yaml.safe_load(actual.split("[attribute_restrictions]\n", 1)[1])

        assert "[attribute_restrictions]" in actual
        assert actual_yaml["changed"][0]["attribute_name_en"] == "truncated"
        assert actual_yaml["changed"][0]["added_restrictions"] == ["'truncated' is read-only"]

    def test_定型指摘をtextで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"] = [
            _create_inspection_phrase("phrase_occluded", ja="隠れています", en="occluded", vi="bi che"),
            _create_inspection_phrase("phrase_too_dark", ja="暗すぎます", en="too dark", vi="qua toi"),
        ]

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )
        actual_yaml = yaml.safe_load(actual.split("[inspection_phrases]\n", 1)[1])

        assert "[inspection_phrases]" in actual
        assert actual_yaml == {
            "added": ["phrase_too_dark"],
            "removed": ["phrase_blur"],
        }

    def test_定型指摘の名前変更をdetail_textで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"][0]["text"]["messages"][0]["message"] = "ぼやけています2"
        right_specs["inspection_phrases"][0]["text"]["messages"][1]["message"] = "blurred2"
        right_specs["inspection_phrases"][0]["text"]["messages"][2]["message"] = "mo2"

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        actual_yaml = yaml.safe_load(actual.split("[inspection_phrases]\n", 1)[1])

        assert actual_yaml["changed"] == [
            {
                "inspection_phrase_id": "phrase_blur",
                "changes": {
                    "inspection_phrase_name_en": {"left": "blurred", "right": "blurred2"},
                    "inspection_phrase_name_ja": {"left": "ぼやけています", "right": "ぼやけています2"},
                    "inspection_phrase_name_vi": {"left": "mo", "right": "mo2"},
                },
            }
        ]

    def test_metadataをtextで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        left_specs["metadata"] = {"removed_key": "削除", "changed_key": 1}
        right_specs["metadata"] = {"changed_key": 2, "added_key": "追加"}

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=False,
        )
        actual_yaml = yaml.safe_load(actual.split("[metadata]\n", 1)[1])

        assert actual_yaml == {
            "added": ["added_key"],
            "removed": ["removed_key"],
            "changed": ["changed_key"],
        }

    def test_metadataをdetail_textで出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        left_specs["metadata"] = {"removed_key": "削除", "changed_key": {"version": 1}}
        right_specs["metadata"] = {"changed_key": {"version": 2}, "added_key": ["追加"]}

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(
            diff,
            left_specs=left_specs,
            right_specs=right_specs,
            detail=True,
        )
        actual_yaml = yaml.safe_load(actual.split("[metadata]\n", 1)[1])

        assert actual_yaml == {
            "added": ["added_key"],
            "removed": ["removed_key"],
            "changed": [{"key": "changed_key", "left": '{"version": 1}', "right": '{"version": 2}'}],
        }


@pytest.mark.access_webapi
class TestCommandLine:
    def test_json形式でlabelsのみ出力できる(self, tmp_path):
        left_specs_path = tmp_path / "left.json"
        right_specs_path = tmp_path / "right.json"
        output_path = tmp_path / "out.json"

        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["color"] = {"red": 0, "green": 255, "blue": 0}

        left_specs_path.write_text(json.dumps(left_specs, ensure_ascii=False), encoding="utf-8")
        right_specs_path.write_text(json.dumps(right_specs, ensure_ascii=False), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "diff",
                "--left_annotation_specs_json",
                str(left_specs_path),
                "--right_annotation_specs_json",
                str(right_specs_path),
                "--target",
                "labels",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        actual = json.loads(output_path.read_text(encoding="utf-8"))

        assert set(actual.keys()) == {"labels"}
        assert actual["labels"]["changed_labels"][0]["label_id"] == "label_car"

    def test_json形式でattribute_restrictionsのみ出力できる(self, tmp_path):
        left_specs_path = tmp_path / "left.json"
        right_specs_path = tmp_path / "right.json"
        output_path = tmp_path / "out.json"

        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["restrictions"] = [
            _create_restriction("attr_occluded", {"_type": "Equals", "value": "choice_yes"}),
        ]

        left_specs_path.write_text(json.dumps(left_specs, ensure_ascii=False), encoding="utf-8")
        right_specs_path.write_text(json.dumps(right_specs, ensure_ascii=False), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "diff",
                "--left_annotation_specs_json",
                str(left_specs_path),
                "--right_annotation_specs_json",
                str(right_specs_path),
                "--target",
                "attribute_restrictions",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        actual = json.loads(output_path.read_text(encoding="utf-8"))

        assert set(actual.keys()) == {"attribute_restrictions"}
        assert actual["attribute_restrictions"]["changed_attribute_restrictions"][0]["attribute_id"] == "attr_occluded"

    def test_detail_text形式で出力できる(self, tmp_path):
        left_specs_path = tmp_path / "left.json"
        right_specs_path = tmp_path / "right.json"
        output_path = tmp_path / "out.txt"

        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["additionals"][0]["default"] = "choice_no"

        left_specs_path.write_text(json.dumps(left_specs, ensure_ascii=False), encoding="utf-8")
        right_specs_path.write_text(json.dumps(right_specs, ensure_ascii=False), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "diff",
                "--left_annotation_specs_json",
                str(left_specs_path),
                "--right_annotation_specs_json",
                str(right_specs_path),
                "--format",
                "detail_text",
                "--output",
                str(output_path),
            ]
        )

        actual = output_path.read_text(encoding="utf-8")
        actual_yaml = yaml.safe_load(actual.split("[attributes]\n", 1)[1])

        assert "[attributes]" in actual
        assert actual_yaml["changed"][0]["changes"]["default"] == {"left": "choice_yes", "right": "choice_no"}

    def test_json形式でinspection_phrasesのみ出力できる(self, tmp_path):
        left_specs_path = tmp_path / "left.json"
        right_specs_path = tmp_path / "right.json"
        output_path = tmp_path / "out.json"

        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["inspection_phrases"] = [
            _create_inspection_phrase("phrase_occluded", ja="隠れています", en="occluded", vi="bi che"),
            _create_inspection_phrase("phrase_too_dark", ja="暗すぎます", en="too dark", vi="qua toi"),
        ]

        left_specs_path.write_text(json.dumps(left_specs, ensure_ascii=False), encoding="utf-8")
        right_specs_path.write_text(json.dumps(right_specs, ensure_ascii=False), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "diff",
                "--left_annotation_specs_json",
                str(left_specs_path),
                "--right_annotation_specs_json",
                str(right_specs_path),
                "--target",
                "inspection_phrases",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        actual = json.loads(output_path.read_text(encoding="utf-8"))

        assert set(actual.keys()) == {"inspection_phrases"}
        assert actual["inspection_phrases"] == {
            "added_inspection_phrase_ids": ["phrase_too_dark"],
            "removed_inspection_phrase_ids": ["phrase_blur"],
            "changed_inspection_phrases": [],
        }

    def test_json形式でmetadataのみ出力できる(self, tmp_path):
        left_specs_path = tmp_path / "left.json"
        right_specs_path = tmp_path / "right.json"
        output_path = tmp_path / "out.json"

        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        left_specs["metadata"] = {"removed_key": "削除", "changed_key": 1}
        right_specs["metadata"] = {"changed_key": 2, "added_key": "追加"}

        left_specs_path.write_text(json.dumps(left_specs, ensure_ascii=False), encoding="utf-8")
        right_specs_path.write_text(json.dumps(right_specs, ensure_ascii=False), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "diff",
                "--left_annotation_specs_json",
                str(left_specs_path),
                "--right_annotation_specs_json",
                str(right_specs_path),
                "--target",
                "metadata",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        actual = json.loads(output_path.read_text(encoding="utf-8"))

        assert set(actual.keys()) == {"metadata"}
        assert actual["metadata"] == {
            "added_metadata_keys": ["added_key"],
            "removed_metadata_keys": ["removed_key"],
            "changed_metadata_keys": ["changed_key"],
        }


class TestAnnotationSpecsDiffCommand:
    def test_差分がないときは標準出力せずログを出力する(self, capsys, caplog):
        command = AnnotationSpecsDiffCommand(
            cast(annofabapi.Resource, None),
            cast(AnnofabApiFacade, None),
            argparse.Namespace(yes=False, output=None, format="text"),
        )

        with caplog.at_level("INFO", logger="annofabcli.annotation_specs.diff_annotation_specs"):
            command.output_text("")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "差分はありません。" in caplog.text
