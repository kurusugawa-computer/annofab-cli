from __future__ import annotations

import copy
import json

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.diff_text_formatter import format_annotation_specs_diff_as_text


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
                    "name_ja_changed": True,
                    "name_en_changed": False,
                    "name_vi_changed": False,
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
                            "name_ja_changed": False,
                            "name_en_changed": False,
                            "name_vi_changed": True,
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


class TestFormatAnnotationSpecsDiffAsText:
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

        assert "label_id:" not in actual
        assert "attribute_id:" not in actual
        assert "choice_id:" not in actual
        assert "label_name_en: car" in actual
        assert "added_attributes:\n    - pose" in actual
        assert "removed_attributes:\n    - truncated" in actual

    def test_detail_textで変更前後の値を出力できる(self):
        left_specs = _create_annotation_specs()
        right_specs = copy.deepcopy(left_specs)
        right_specs["labels"][0]["label_name"]["messages"][0]["message"] = "自動車"
        right_specs["additionals"][0]["name"]["messages"][2]["message"] = "co-moi"

        diff = create_annotation_specs_diff(left_specs, right_specs)
        actual = format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=True)

        assert "[labels]" in actual
        assert 'label_name_ja: "車" -> "自動車"' in actual
        assert "[attributes]" in actual
        assert 'name_vi: "bị che" -> "co-moi"' in actual
        assert "attribute_id:" not in actual
        assert "choice_id:" not in actual

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

        assert "attribute_name_en: occluded" in actual
        assert "added_attributes:\n    - pose" in actual
        assert "removed_attributes:\n    - truncated" in actual
        assert "added_choices:\n    - unknown" in actual
        assert "choice_name_en: yes_changed" in actual

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

        assert "[attribute_restrictions]" in actual
        assert "attribute_name_en: occluded" in actual
        assert "added_restrictions:" in actual
        assert "'occluded' is 'yes'" in actual
        assert "attr_occluded" not in actual

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

        assert "[attribute_restrictions]" in actual
        assert "added_restrictions:" in actual
        assert "'truncated' is read-only" in actual
        assert 'condition: {"_type": "CanInput", "enable": false}' in actual


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

        assert "[attributes]" in actual
        assert 'default: "choice_yes" -> "choice_no"' in actual
