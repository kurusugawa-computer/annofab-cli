from __future__ import annotations

import json
from pathlib import Path

import pandas
import pytest

from annofabcli.annotation_specs.update_attributes import (
    AttributeUpdateInput,
    build_request_body_for_update_attributes,
    read_attributes_csv,
    read_attributes_json,
    resolve_attribute_update_inputs,
    validate_attribute_update_inputs,
)

data_dir = Path("./tests/data/annotation_specs")
COMMENT_ATTRIBUTE_ID = "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
UNCLEAR_ATTRIBUTE_ID = "f12a0b59-dfce-4241-bb87-4b2c0259fc6f"


@pytest.fixture
def annotation_specs() -> dict:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestBuildRequestBodyForUpdateAttributes:
    def test_build_request_body_for_update_attributes(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[
                AttributeUpdateInput(
                    attribute_id=COMMENT_ATTRIBUTE_ID,
                    attribute_name_en="remark",
                    attribute_name_ja="コメント",
                    keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                    read_only=True,
                    default_value="確認済み",
                    has_default_value=True,
                ),
                AttributeUpdateInput(
                    attribute_id=UNCLEAR_ATTRIBUTE_ID,
                    default_value="true",
                    has_default_value=True,
                ),
            ],
        )

        actual = build_request_body_for_update_attributes(
            annotation_specs,
            resolved_attribute_update_inputs=resolved_inputs,
            comment=None,
        )

        comment_attribute = next(additional for additional in actual["additionals"] if additional["additional_data_definition_id"] == COMMENT_ATTRIBUTE_ID)
        assert comment_attribute["name"]["messages"] == [
            {"lang": "ja-JP", "message": "コメント"},
            {"lang": "en-US", "message": "remark"},
        ]
        assert comment_attribute["type"] == "comment"
        assert comment_attribute["read_only"] is True
        assert comment_attribute["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]
        assert comment_attribute["default"] == "確認済み"

        unclear_attribute = next(additional for additional in actual["additionals"] if additional["additional_data_definition_id"] == UNCLEAR_ATTRIBUTE_ID)
        assert unclear_attribute["default"] is True
        assert actual["comment"].startswith("以下の属性情報を更新しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

        car_label = next(label for label in actual["labels"] if label["label_id"] == "car_label_id")
        assert car_label["additional_data_definitions"] == annotation_specs["labels"][0]["additional_data_definitions"]

    def test_build_request_body_for_update_attributes__custom_comment(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[AttributeUpdateInput(attribute_id=COMMENT_ATTRIBUTE_ID, attribute_name_ja="コメント")],
        )

        actual = build_request_body_for_update_attributes(
            annotation_specs,
            resolved_attribute_update_inputs=resolved_inputs,
            comment="custom",
        )

        assert actual["comment"] == "custom"

    def test_build_request_body_for_update_attributes__preserves_name_metadata(self, annotation_specs: dict) -> None:
        annotation_specs["additionals"][0]["name"] = {
            "messages": [
                {"lang": "en-US", "message": "comment"},
                {"lang": "ja-JP", "message": "comment"},
                {"lang": "fr-FR", "message": "commentaire"},
            ],
            "default_lang": "en-US",
        }
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[AttributeUpdateInput(attribute_id=COMMENT_ATTRIBUTE_ID, attribute_name_en="remark", attribute_name_ja="コメント")],
        )

        actual = build_request_body_for_update_attributes(
            annotation_specs,
            resolved_attribute_update_inputs=resolved_inputs,
            comment=None,
        )

        comment_attribute = next(additional for additional in actual["additionals"] if additional["additional_data_definition_id"] == COMMENT_ATTRIBUTE_ID)
        assert comment_attribute["name"] == {
            "messages": [
                {"lang": "en-US", "message": "remark"},
                {"lang": "ja-JP", "message": "コメント"},
                {"lang": "fr-FR", "message": "commentaire"},
            ],
            "default_lang": "en-US",
        }

    def test_build_request_body_for_update_attributes__invalid_default_value(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[
                AttributeUpdateInput(
                    attribute_id=UNCLEAR_ATTRIBUTE_ID,
                    default_value="yes",
                    has_default_value=True,
                )
            ],
        )

        with pytest.raises(ValueError):
            build_request_body_for_update_attributes(
                annotation_specs,
                resolved_attribute_update_inputs=resolved_inputs,
                comment=None,
            )

    def test_build_request_body_for_update_attributes__同じラベル内で属性名英語が重複していたらエラー(self, annotation_specs: dict) -> None:
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[AttributeUpdateInput(attribute_id=UNCLEAR_ATTRIBUTE_ID, attribute_name_en="comment")],
        )

        with pytest.raises(ValueError):
            build_request_body_for_update_attributes(
                annotation_specs,
                resolved_attribute_update_inputs=resolved_inputs,
                comment=None,
            )

    def test_build_request_body_for_update_attributes__異なるラベルなら属性名英語が重複していてもよい(self, annotation_specs: dict) -> None:
        bike_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "40f7796b-3722-4eed-9c0c-04a27f9165d2")
        bike_label["additional_data_definitions"] = [UNCLEAR_ATTRIBUTE_ID]
        car_label = next(label for label in annotation_specs["labels"] if label["label_id"] == "car_label_id")
        car_label["additional_data_definitions"] = [COMMENT_ATTRIBUTE_ID]
        resolved_inputs = resolve_attribute_update_inputs(
            annotation_specs,
            attribute_update_inputs=[AttributeUpdateInput(attribute_id=UNCLEAR_ATTRIBUTE_ID, attribute_name_en="comment")],
        )

        actual = build_request_body_for_update_attributes(
            annotation_specs,
            resolved_attribute_update_inputs=resolved_inputs,
            comment=None,
        )

        unclear_attribute = next(additional for additional in actual["additionals"] if additional["additional_data_definition_id"] == UNCLEAR_ATTRIBUTE_ID)
        assert unclear_attribute["name"]["messages"] == [
            {"lang": "ja-JP", "message": "unclear"},
            {"lang": "en-US", "message": "comment"},
        ]


class TestResolveAttributeUpdateInputs:
    def test_resolve_attribute_update_inputs__attribute_not_found(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_update_inputs(
                annotation_specs,
                attribute_update_inputs=[AttributeUpdateInput(attribute_id="not-found", attribute_name_ja="dummy")],
            )

    def test_resolve_attribute_update_inputs__same_attribute(self, annotation_specs: dict) -> None:
        with pytest.raises(ValueError):
            resolve_attribute_update_inputs(
                annotation_specs,
                attribute_update_inputs=[
                    AttributeUpdateInput(attribute_id=COMMENT_ATTRIBUTE_ID, attribute_name_ja="コメント"),
                    AttributeUpdateInput(attribute_id=COMMENT_ATTRIBUTE_ID, read_only=True),
                ],
            )


class TestAttributeUpdateInputs:
    def test_validate_attribute_update_inputs__duplicated_attribute_id(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_update_inputs(
                [
                    AttributeUpdateInput(attribute_id="comment", attribute_name_ja="コメント"),
                    AttributeUpdateInput(attribute_id="comment", read_only=True),
                ]
            )

    def test_validate_attribute_update_inputs__empty(self) -> None:
        with pytest.raises(ValueError):
            validate_attribute_update_inputs([])


class TestReadAttributes:
    def test_read_attributes_json(self) -> None:
        actual = read_attributes_json(
            f'[{{"attribute_id":"{COMMENT_ATTRIBUTE_ID}","attribute_name_en":"remark","attribute_name_ja":"コメント",'
            '"keybind":{"alt":false,"code":"Digit1","ctrl":true,"shift":false},'
            '"read_only":true,"default_value":"確認済み"},'
            f'{{"attribute_id":"{UNCLEAR_ATTRIBUTE_ID}","default_value":true}}]'
        )

        assert actual == [
            AttributeUpdateInput(
                attribute_id=COMMENT_ATTRIBUTE_ID,
                attribute_name_en="remark",
                attribute_name_ja="コメント",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                read_only=True,
                default_value="確認済み",
                has_default_value=True,
            ),
            AttributeUpdateInput(
                attribute_id=UNCLEAR_ATTRIBUTE_ID,
                default_value=True,
                has_default_value=True,
            ),
        ]

    def test_read_attributes_json__label_id_is_not_allowed(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_name_en":"comment","attribute_name_ja":"コメント","label_id":"car_label_id"}]')

    def test_read_attributes_json__target_required(self) -> None:
        with pytest.raises(ValueError):
            read_attributes_json('[{"attribute_name_ja":"コメント"}]')

    def test_read_attributes_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "attributes.csv"
        df = pandas.DataFrame(
            [
                {
                    "attribute_id": COMMENT_ATTRIBUTE_ID,
                    "attribute_name_en": "remark",
                    "attribute_name_ja": "コメント",
                    "keybind": '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}',
                    "read_only": "true",
                    "default_value": "確認済み",
                },
                {"attribute_id": UNCLEAR_ATTRIBUTE_ID, "default_value": "true"},
            ]
        )
        df.to_csv(csv_path, index=False)

        actual = read_attributes_csv(csv_path)

        assert actual == [
            AttributeUpdateInput(
                attribute_id=COMMENT_ATTRIBUTE_ID,
                attribute_name_en="remark",
                attribute_name_ja="コメント",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                read_only=True,
                default_value="確認済み",
                has_default_value=True,
            ),
            AttributeUpdateInput(
                attribute_id=UNCLEAR_ATTRIBUTE_ID,
                default_value="true",
                has_default_value=True,
            ),
        ]
