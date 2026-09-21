from __future__ import annotations

from annofabcli.annotation_specs.describe_label_attributes import DescriptionLanguage, create_label_attributes_description


def test_ラベルと属性の関係を日本語で記述する() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {"messages": [{"lang": "en-US", "message": "car"}, {"lang": "ja-JP", "message": "車"}]},
                "annotation_type": "bounding_box",
                "additional_data_definitions": ["attribute_direction", "attribute_occluded"],
            },
            {
                "label_name": {"messages": [{"lang": "en-US", "message": "road"}, {"lang": "ja-JP", "message": "道路"}]},
                "annotation_type": "segmentation_v2",
                "additional_data_definitions": [],
            },
        ],
        "additionals": [
            {
                "additional_data_definition_id": "attribute_direction",
                "name": {"messages": [{"lang": "en-US", "message": "direction"}, {"lang": "ja-JP", "message": "向き"}]},
                "type": "select",
                "read_only": False,
                "choices": [
                    {"name": {"messages": [{"lang": "en-US", "message": "front"}, {"lang": "ja-JP", "message": "前"}]}},
                    {"name": {"messages": [{"lang": "en-US", "message": "side"}, {"lang": "ja-JP", "message": "横"}]}},
                ],
            },
            {
                "additional_data_definition_id": "attribute_occluded",
                "name": {"messages": [{"lang": "en-US", "message": "occluded"}, {"lang": "ja-JP", "message": "遮蔽"}]},
                "type": "flag",
                "read_only": True,
                "choices": [],
            },
        ],
    }

    actual = create_label_attributes_description(annotation_specs, DescriptionLanguage.JA)

    assert (
        actual
        == """# 「車」ラベル（矩形）

- 「向き」属性（ドロップダウン）
  - 前
  - 横
- 「遮蔽」属性（真偽値、読み込み専用）

# 「道路」ラベル（セマンティックセグメンテーション）

- 属性なし"""
    )


def test_ラベルと属性の関係を英語で記述する() -> None:
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
                "type": "choice",
                "read_only": True,
                "choices": [{"name": {"messages": [{"lang": "en-US", "message": "front"}]}}],
            }
        ],
    }

    actual = create_label_attributes_description(annotation_specs, DescriptionLanguage.EN)

    assert (
        actual
        == """# Label "car" (Bounding box)

- Attribute "direction" (Radio button, read-only)
  - front"""
    )


def test_Markdownを崩す名前をエスケープする() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {"messages": [{"lang": "ja-JP", "message": "# 車"}]},
                "annotation_type": "point",
                "additional_data_definitions": ["attribute_name"],
            }
        ],
        "additionals": [
            {
                "additional_data_definition_id": "attribute_name",
                "name": {"messages": [{"lang": "ja-JP", "message": "*名称*"}]},
                "type": "text",
                "read_only": False,
                "choices": [],
            }
        ],
    }

    actual = create_label_attributes_description(annotation_specs, DescriptionLanguage.JA)

    assert (
        actual
        == """# 「\\# 車」ラベル（点）

- 「\\*名称\\*」属性（テキスト）"""
    )
