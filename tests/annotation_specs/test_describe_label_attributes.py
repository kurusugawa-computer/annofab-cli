from __future__ import annotations

import argparse
from unittest.mock import Mock

from annofabcli.annotation_specs.describe_label_attributes import DescribeLabelAttributes, DescriptionLanguage, create_label_attributes_description


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
- 「遮蔽」属性（チェックボックス、読み込み専用）

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
                "name": {"messages": [{"lang": "ja-JP", "message": "*名称*_id"}]},
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

- 「\\*名称\\*_id」属性（1行テキスト）"""
    )


def test_テキスト属性の入力行数を日本語で記述する() -> None:
    annotation_specs = {
        "labels": [
            {
                "label_name": {"messages": [{"lang": "ja-JP", "message": "車"}]},
                "annotation_type": "bounding_box",
                "additional_data_definitions": ["attribute_id", "attribute_note"],
            }
        ],
        "additionals": [
            {
                "additional_data_definition_id": "attribute_id",
                "name": {"messages": [{"lang": "ja-JP", "message": "ID"}]},
                "type": "text",
                "read_only": False,
                "choices": [],
            },
            {
                "additional_data_definition_id": "attribute_note",
                "name": {"messages": [{"lang": "ja-JP", "message": "備考"}]},
                "type": "comment",
                "read_only": False,
                "choices": [],
            },
        ],
    }

    actual = create_label_attributes_description(annotation_specs, DescriptionLanguage.JA)

    assert (
        actual
        == """# 「車」ラベル（矩形）

- 「ID」属性（1行テキスト）
- 「備考」属性（複数行テキスト）"""
    )


def test_beforeは履歴の返却順に関わらず更新日時の新しい順に選択する() -> None:
    service = Mock()
    service.api.get_annotation_specs_histories.return_value = (
        [
            {"history_id": "history_2", "updated_datetime": "2026-09-02T00:00:00Z", "comment": "2番目"},
            {"history_id": "history_0", "updated_datetime": "2026-09-03T00:00:00Z", "comment": "最新"},
            {"history_id": "history_1", "updated_datetime": "2026-09-01T00:00:00Z", "comment": "最古"},
        ],
        None,
    )
    command = DescribeLabelAttributes(service, Mock(), argparse.Namespace(yes=False))

    actual = command.get_history_id_from_before_index("project_id", before=1)

    assert actual == "history_2"
