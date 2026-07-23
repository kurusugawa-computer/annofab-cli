from __future__ import annotations

import json
from pathlib import Path

import pytest

from annofabcli.__main__ import main

DATA_DIR = Path("./tests/data/annotation_specs")

pytestmark = pytest.mark.access_webapi


class TestListAttributeRestriction:
    command_name = "annotation_specs"

    def test_text形式で人が読みやすい属性制約を出力する(self, tmp_path: Path) -> None:
        annotation_specs_path = DATA_DIR / "annotation_specs.json"
        output_path = tmp_path / "restrictions.txt"

        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--annotation_specs_json_file",
                str(annotation_specs_path),
                "--attribute_name_en",
                "comment",
                "--format",
                "text",
                "--output",
                str(output_path),
            ]
        )

        actual_text = output_path.read_text(encoding="utf-8")

        assert actual_text == (
            "'comment' is read-only\n"
            "'comment' is not empty\n"
            "'comment' is 'foo'\n"
            "'comment' is not 'bar'\n"
            "'comment' matches '[abc]+'\n"
            "'comment' does not match '[0-9]+'\n"
            "If 'unclear' is checked, 'comment' matches '[0-9]'."
        )

    def test_json形式で属性制約のJSONをそのまま出力する(self, tmp_path: Path) -> None:
        annotation_specs_path = DATA_DIR / "annotation_specs.json"
        output_path = tmp_path / "restrictions.json"

        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--annotation_specs_json_file",
                str(annotation_specs_path),
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        with annotation_specs_path.open(encoding="utf-8") as f:
            annotation_specs = json.load(f)
        with output_path.open(encoding="utf-8") as f:
            actual = json.load(f)

        assert actual == annotation_specs["restrictions"]

    def test_pretty_json形式で絞り込み後の属性制約を整形出力する(self, tmp_path: Path) -> None:
        annotation_specs_path = DATA_DIR / "annotation_specs.json"
        output_path = tmp_path / "restrictions_pretty.json"

        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--annotation_specs_json_file",
                str(annotation_specs_path),
                "--attribute_name_en",
                "link",
                "--format",
                "pretty_json",
                "--output",
                str(output_path),
            ]
        )

        actual_text = output_path.read_text(encoding="utf-8")
        actual = json.loads(actual_text)

        assert actual == [
            {
                "additional_data_definition_id": "15235360-4f46-42ac-927d-0e046bf52ddd",
                "condition": {
                    "labels": [
                        "40f7796b-3722-4eed-9c0c-04a27f9165d2",
                        "22b5189b-af7b-4d9c-83a5-b92f122170ec",
                    ],
                    "_type": "HasLabel",
                },
            }
        ]
        assert "\n  {" in actual_text

    def test_pretty_json形式で属性IDに紐づく属性制約を出力する(self, tmp_path: Path) -> None:
        annotation_specs_path = DATA_DIR / "annotation_specs.json"
        output_path = tmp_path / "restrictions_pretty.json"

        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--annotation_specs_json_file",
                str(annotation_specs_path),
                "--attribute_id",
                "15235360-4f46-42ac-927d-0e046bf52ddd",
                "--format",
                "pretty_json",
                "--output",
                str(output_path),
            ]
        )

        actual = json.loads(output_path.read_text(encoding="utf-8"))

        assert actual == [
            {
                "additional_data_definition_id": "15235360-4f46-42ac-927d-0e046bf52ddd",
                "condition": {
                    "labels": [
                        "40f7796b-3722-4eed-9c0c-04a27f9165d2",
                        "22b5189b-af7b-4d9c-83a5-b92f122170ec",
                    ],
                    "_type": "HasLabel",
                },
            }
        ]

    def test_restriction_typeを指定したときは一致する種類だけ出力する(self, tmp_path: Path) -> None:
        annotation_specs_path = DATA_DIR / "annotation_specs.json"
        output_path = tmp_path / "restrictions_by_type.json"

        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--annotation_specs_json_file",
                str(annotation_specs_path),
                "--attribute_name_en",
                "comment",
                "--restriction_type",
                "imply",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

        with output_path.open(encoding="utf-8") as f:
            actual = json.load(f)

        assert actual == [
            {
                "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                "condition": {
                    "premise": {
                        "additional_data_definition_id": "f12a0b59-dfce-4241-bb87-4b2c0259fc6f",
                        "condition": {"value": "true", "_type": "Equals"},
                    },
                    "condition": {"value": "[0-9]", "_type": "Matches"},
                    "_type": "Imply",
                },
            }
        ]
