from __future__ import annotations

import json

import pandas
import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_specs.list_annotation_specs_inspection_phrase import create_inspection_phrase_list


def create_annotation_specs_json(inspection_phrases: list[dict]) -> dict:
    return {
        "format_version": "3.0.0",
        "labels": [],
        "additionals": [],
        "restrictions": [],
        "inspection_phrases": inspection_phrases,
        "metadata": {},
    }


def create_inspection_phrase(phrase_id: str, *, en: str, ja: str, vi: str) -> dict:
    return {
        "id": phrase_id,
        "text": {
            "messages": [
                {"lang": "en-US", "message": en},
                {"lang": "ja-JP", "message": ja},
                {"lang": "vi-VN", "message": vi},
            ],
            "default_lang": "ja-JP",
        },
    }


class TestCreateInspectionPhraseList:
    def test_定型指摘の各言語の本文を抽出できる(self) -> None:
        actual = create_inspection_phrase_list(
            [
                create_inspection_phrase(
                    "phrase_blur",
                    en="blurred",
                    ja="ぼやけています",
                    vi="mo",
                )
            ]
        )

        assert len(actual) == 1
        assert actual[0].inspection_phrase_id == "phrase_blur"
        assert actual[0].inspection_phrase_text_en == "blurred"
        assert actual[0].inspection_phrase_text_ja == "ぼやけています"
        assert actual[0].inspection_phrase_text_vi == "mo"

    def test_空配列なら空リストを返す(self) -> None:
        assert create_inspection_phrase_list([]) == []


@pytest.mark.access_webapi
class TestCommandLine:
    def test_annotation_specs_jsonからcsv出力できる(self, tmp_path) -> None:
        annotation_specs_path = tmp_path / "annotation_specs.json"
        output_path = tmp_path / "inspection_phrases.csv"
        annotation_specs_path.write_text(
            json.dumps(
                create_annotation_specs_json(
                    [
                        create_inspection_phrase(
                            "phrase_blur",
                            en="blurred",
                            ja="ぼやけています",
                            vi="mo",
                        )
                    ]
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        main(
            [
                "annotation_specs",
                "list_inspection_phrase",
                "--annotation_specs_json",
                str(annotation_specs_path),
                "--output",
                str(output_path),
            ]
        )

        df = pandas.read_csv(output_path)

        assert list(df.columns) == [
            "inspection_phrase_id",
            "inspection_phrase_text_en",
            "inspection_phrase_text_ja",
            "inspection_phrase_text_vi",
        ]
        assert df.loc[0, "inspection_phrase_id"] == "phrase_blur"
        assert df.loc[0, "inspection_phrase_text_ja"] == "ぼやけています"

    def test_定型指摘が0件でもcsvヘッダを出力する(self, tmp_path) -> None:
        annotation_specs_path = tmp_path / "annotation_specs.json"
        output_path = tmp_path / "inspection_phrases.csv"
        annotation_specs_path.write_text(json.dumps(create_annotation_specs_json([])), encoding="utf-8")

        main(
            [
                "annotation_specs",
                "list_inspection_phrase",
                "--annotation_specs_json",
                str(annotation_specs_path),
                "--output",
                str(output_path),
            ]
        )

        assert output_path.read_text(encoding="utf-8-sig") == "inspection_phrase_id,inspection_phrase_text_en,inspection_phrase_text_ja,inspection_phrase_text_vi\n"
