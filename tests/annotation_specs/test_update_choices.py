from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pandas
import pytest

from annofabcli.annotation_specs.update_choices import (
    ChoiceUpdateInput,
    build_request_body_for_update_choices,
    read_choices_csv,
    read_choices_json,
    resolve_choice_update_inputs,
    validate_choice_update_inputs,
)

DATA_DIR = Path("./tests/data/annotation_specs")
TYPE_ATTRIBUTE_ID = "71620647-98cf-48ad-b43b-4af425a24f32"
LARGE_CHOICE_ID = "08ec927c-18e6-4bba-837a-b16de7061580"
SMALL_CHOICE_ID = "74691a87-7962-4fa9-ba52-7cc466ecd982"


@pytest.fixture
def annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        loaded_annotation_specs = json.load(f)
    loaded_annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return loaded_annotation_specs


class TestBuildRequestBodyForUpdateChoices:
    def test_build_request_body_for_update_choices(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_choice_update_inputs(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_update_inputs=[
                ChoiceUpdateInput(
                    choice_name_en="large",
                    choice_name_ja="大",
                    keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                    has_keybind=True,
                ),
                ChoiceUpdateInput(choice_id=SMALL_CHOICE_ID, keybind=None, has_keybind=True),
            ],
        )

        actual = build_request_body_for_update_choices(annotation_specs, resolved_choice_update_inputs=resolved_inputs, comment=None)

        type_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID)
        large_choice = next(choice for choice in type_attribute["choices"] if choice["choice_id"] == LARGE_CHOICE_ID)
        assert large_choice["name"]["messages"] == [
            {"lang": "ja-JP", "message": "大"},
            {"lang": "en-US", "message": "large"},
        ]
        assert large_choice["keybind"] == [{"alt": False, "code": "Digit1", "ctrl": True, "shift": False}]

        small_choice = next(choice for choice in type_attribute["choices"] if choice["choice_id"] == SMALL_CHOICE_ID)
        assert small_choice["keybind"] == []
        assert type_attribute["default"] == ""
        assert actual["comment"].startswith("以下の選択肢情報を更新しました。")
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"

    def test_build_request_body_for_update_choices__custom_comment(self, annotation_specs: dict[str, Any]) -> None:
        resolved_inputs = resolve_choice_update_inputs(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_update_inputs=[ChoiceUpdateInput(choice_name_en="large", choice_name_ja="大")],
        )

        actual = build_request_body_for_update_choices(annotation_specs, resolved_choice_update_inputs=resolved_inputs, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_update_choices__preserves_name_metadata(self, annotation_specs: dict[str, Any]) -> None:
        target_attribute = next(attribute for attribute in annotation_specs["additionals"] if attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID)
        target_attribute["choices"][0]["name"] = {
            "messages": [
                {"lang": "en-US", "message": "large"},
                {"lang": "ja-JP", "message": "large"},
                {"lang": "fr-FR", "message": "grand"},
            ],
            "default_lang": "en-US",
        }
        resolved_inputs = resolve_choice_update_inputs(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_update_inputs=[ChoiceUpdateInput(choice_name_en="large", choice_name_ja="大")],
        )

        actual = build_request_body_for_update_choices(annotation_specs, resolved_choice_update_inputs=resolved_inputs, comment=None)

        type_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID)
        large_choice = next(choice for choice in type_attribute["choices"] if choice["choice_id"] == LARGE_CHOICE_ID)
        assert large_choice["name"] == {
            "messages": [
                {"lang": "en-US", "message": "large"},
                {"lang": "ja-JP", "message": "大"},
                {"lang": "fr-FR", "message": "grand"},
            ],
            "default_lang": "en-US",
        }

    def test_build_request_body_for_update_choices__元のアノテーション仕様は変更しない(self, annotation_specs: dict[str, Any]) -> None:
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved_inputs = resolve_choice_update_inputs(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_update_inputs=[ChoiceUpdateInput(choice_name_en="large", choice_name_ja="大")],
        )

        build_request_body_for_update_choices(annotation_specs, resolved_choice_update_inputs=resolved_inputs, comment=None)

        assert annotation_specs == old_annotation_specs


class TestResolveChoiceUpdateInputs:
    def test_resolve_choice_update_inputs__attribute_id(self, annotation_specs: dict[str, Any]) -> None:
        actual = resolve_choice_update_inputs(
            annotation_specs,
            attribute_id=TYPE_ATTRIBUTE_ID,
            attribute_name_en=None,
            choice_update_inputs=[ChoiceUpdateInput(choice_name_en="large", choice_name_ja="大")],
        )

        assert actual[0].target_attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID
        assert actual[0].target_choice["choice_id"] == LARGE_CHOICE_ID

    def test_resolve_choice_update_inputs__attribute_not_choice(self, annotation_specs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            resolve_choice_update_inputs(
                annotation_specs,
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                choice_update_inputs=[ChoiceUpdateInput(choice_name_en="large", choice_name_ja="大")],
            )

    def test_resolve_choice_update_inputs__choice_not_found(self, annotation_specs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            resolve_choice_update_inputs(
                annotation_specs,
                attribute_id=None,
                attribute_name_en="type",
                choice_update_inputs=[ChoiceUpdateInput(choice_name_en="not-found", choice_name_ja="なし")],
            )

    def test_resolve_choice_update_inputs__same_choice_by_different_keys(self, annotation_specs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            resolve_choice_update_inputs(
                annotation_specs,
                attribute_id=None,
                attribute_name_en="type",
                choice_update_inputs=[
                    ChoiceUpdateInput(choice_id=LARGE_CHOICE_ID, choice_name_ja="大"),
                    ChoiceUpdateInput(choice_name_en="large", keybind=None, has_keybind=True),
                ],
            )


class TestChoiceUpdateInputs:
    def test_validate_choice_update_inputs__duplicated_choice_id(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_update_inputs(
                [
                    ChoiceUpdateInput(choice_id="large", choice_name_ja="大"),
                    ChoiceUpdateInput(choice_id="large", keybind=None, has_keybind=True),
                ]
            )

    def test_validate_choice_update_inputs__empty(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_update_inputs([])


class TestReadChoices:
    def test_read_choices_json(self) -> None:
        actual = read_choices_json(
            f'[{{"choice_name_en":"large","choice_name_ja":"大","keybind":{{"alt":false,"code":"Digit1","ctrl":true,"shift":false}}}},{{"choice_id":"{SMALL_CHOICE_ID}","keybind":null}}]'
        )

        assert actual == [
            ChoiceUpdateInput(
                choice_name_en="large",
                choice_name_ja="大",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                has_keybind=True,
            ),
            ChoiceUpdateInput(choice_id=SMALL_CHOICE_ID, keybind=None, has_keybind=True),
        ]

    def test_read_choices_json__unexpected_key(self) -> None:
        with pytest.raises(ValueError):
            read_choices_json('[{"choice_name_en":"large","choice_name_ja":"大","is_default":true}]')

    def test_read_choices_json__target_required(self) -> None:
        with pytest.raises(ValueError):
            read_choices_json('[{"choice_name_ja":"大"}]')

    def test_read_choices_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        df = pandas.DataFrame(
            [
                {
                    "choice_name_en": "large",
                    "choice_name_ja": "大",
                    "keybind": '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}',
                },
                {"choice_id": SMALL_CHOICE_ID, "choice_name_ja": "小"},
            ]
        )
        df.to_csv(csv_path, index=False)

        actual = read_choices_csv(csv_path)

        assert actual == [
            ChoiceUpdateInput(
                choice_name_en="large",
                choice_name_ja="大",
                keybind={"alt": False, "code": "Digit1", "ctrl": True, "shift": False},
                has_keybind=True,
            ),
            ChoiceUpdateInput(choice_id=SMALL_CHOICE_ID, choice_name_ja="小"),
        ]

    def test_read_choices_csv__invalid_keybind(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "choices.csv"
        df = pandas.DataFrame([{"choice_name_en": "large", "keybind": "invalid"}])
        df.to_csv(csv_path, index=False)

        with pytest.raises(ValueError):
            read_choices_csv(csv_path)
