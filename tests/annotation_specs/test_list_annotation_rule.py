from __future__ import annotations

from annofabcli.annotation_specs.list_annotation_rule import AnnotationRuleLanguage, create_annotation_rule_text


def test_アノテーションルールを日本語で出力する() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {
                    "messages": [
                        {"lang": "en-US", "message": "car"},
                        {"lang": "ja-JP", "message": "車"},
                    ]
                },
                "annotation_type": "bounding_box",
                "additional_data_definitions": ["attribute_direction", "attribute_occluded"],
                "color": {"red": 255, "green": 0, "blue": 0},
                "keybind": [],
            },
            {
                "label_name": {
                    "messages": [
                        {"lang": "en-US", "message": "road"},
                        {"lang": "ja-JP", "message": "道路"},
                    ]
                },
                "annotation_type": "segmentation_v2",
                "additional_data_definitions": [],
            },
        ],
        "additionals": [
            {
                "additional_data_definition_id": "attribute_direction",
                "name": {
                    "messages": [
                        {"lang": "en-US", "message": "direction"},
                        {"lang": "ja-JP", "message": "向き"},
                    ]
                },
                "type": "select",
                "choices": [
                    {
                        "name": {
                            "messages": [
                                {"lang": "en-US", "message": "front"},
                                {"lang": "ja-JP", "message": "前"},
                            ]
                        }
                    },
                    {
                        "name": {
                            "messages": [
                                {"lang": "en-US", "message": "side"},
                                {"lang": "ja-JP", "message": "横"},
                            ]
                        }
                    },
                ],
                "keybind": [],
            },
            {
                "additional_data_definition_id": "attribute_occluded",
                "name": {
                    "messages": [
                        {"lang": "en-US", "message": "occluded"},
                        {"lang": "ja-JP", "message": "遮蔽"},
                    ]
                },
                "type": "flag",
                "choices": [],
                "read_only": True,
            },
        ],
        "restrictions": [{"additional_data_definition_id": "attribute_direction"}],
    }

    actual = create_annotation_rule_text(annotation_specs, AnnotationRuleLanguage.JA)

    assert (
        actual
        == """# アノテーションルール

## 車
- アノテーションの種類: `bounding_box`
- 属性:
  - 向き: `select`
    - 選択肢:
      - 前
      - 横
  - 遮蔽: `flag`

## 道路
- アノテーションの種類: `segmentation_v2`
- 属性: なし"""
    )


def test_アノテーションルールを英語で出力する() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {"messages": [{"lang": "en-US", "message": "car"}]},
                "annotation_type": "bounding_box",
                "additional_data_definitions": ["attribute_direction"],
            }
        ],
        "additionals": [
            {
                "additional_data_definition_id": "attribute_direction",
                "name": {"messages": [{"lang": "en-US", "message": "direction"}]},
                "type": "select",
                "choices": [{"name": {"messages": [{"lang": "en-US", "message": "front"}]}}],
            }
        ],
    }

    actual = create_annotation_rule_text(annotation_specs, AnnotationRuleLanguage.EN)

    assert (
        actual
        == """# Annotation rules

## car
- Annotation type: `bounding_box`
- Attributes:
  - direction: `select`
    - Choices:
      - front"""
    )
