from __future__ import annotations

import pandas
import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_specs.list_annotation_specs_label import create_label_list, create_label_list_for_csv


class TestCreateLabelList:
    def test_field_valuesを保持する(self):
        labels_v3 = [
            {
                "label_id": "label_1",
                "label_name": {
                    "messages": [
                        {"lang": "en-US", "message": "car"},
                        {"lang": "ja-JP", "message": "自動車"},
                    ],
                    "default_lang": "ja-JP",
                },
                "annotation_type": "bounding_box",
                "color": {"red": 255, "green": 0, "blue": 0},
                "additional_data_definitions": ["attribute_1"],
                "keybind": [],
                "field_values": {
                    "margin_of_error_tolerance": {
                        "_type": "MarginOfErrorTolerance",
                        "max_pixel": 3,
                    }
                },
            }
        ]

        result = create_label_list(labels_v3)

        assert len(result) == 1
        assert result[0].field_values == {
            "margin_of_error_tolerance": {
                "_type": "MarginOfErrorTolerance",
                "max_pixel": 3,
            }
        }

    def test_field_valuesが無い場合は空辞書にする(self):
        labels_v3 = [
            {
                "label_id": "label_1",
                "label_name": {
                    "messages": [
                        {"lang": "en-US", "message": "car"},
                    ],
                    "default_lang": "en-US",
                },
                "annotation_type": "bounding_box",
                "color": {"red": 255, "green": 0, "blue": 0},
                "additional_data_definitions": [],
                "keybind": [],
            }
        ]

        result = create_label_list(labels_v3)

        assert len(result) == 1
        assert result[0].field_values == {}


class TestCreateLabelListForCsv:
    def test_field_valuesをjson文字列に変換する(self):
        label_list = create_label_list(
            [
                {
                    "label_id": "label_1",
                    "label_name": {
                        "messages": [
                            {"lang": "en-US", "message": "car"},
                            {"lang": "ja-JP", "message": "自動車"},
                        ],
                        "default_lang": "ja-JP",
                    },
                    "annotation_type": "bounding_box",
                    "color": {"red": 255, "green": 0, "blue": 0},
                    "additional_data_definitions": [],
                    "keybind": [],
                    "field_values": {
                        "display_name": {
                            "_type": "DisplayName",
                            "text": "車両",
                        }
                    },
                }
            ]
        )

        result = create_label_list_for_csv(label_list)

        assert len(result) == 1
        assert result[0]["field_values"] == '{"display_name": {"_type": "DisplayName", "text": "車両"}}'


@pytest.mark.access_webapi
class TestCommandLine:
    def test_annotation_specs_jsonからcsv出力できる(self, tmp_path):
        output_path = tmp_path / "labels.csv"

        main(
            [
                "annotation_specs",
                "list_label",
                "--annotation_specs_json",
                "tests/data/annotation/import_annotation/annotation_specs.json",
                "--output",
                str(output_path),
            ]
        )

        df = pandas.read_csv(output_path)

        assert "field_values" in df.columns
        assert df.loc[0, "field_values"].startswith('{"minimum_size_2d_with_default_insert_position":')
