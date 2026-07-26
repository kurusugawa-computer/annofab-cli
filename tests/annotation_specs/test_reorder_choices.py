from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.reorder_choices import (
    build_request_body_for_reorder_choices,
    create_comment_for_reorder_choices,
    create_confirm_message_for_reorder_choices,
    resolve_choice_reorder,
    validate_choice_reorder_inputs,
)

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestResolveChoiceReorder:
    def test_resolve_choice_reorder__name指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small", "large"],
        )

        assert actual.target_attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"
        assert [choice["choice_id"] for choice in actual.first_choices] == [
            "74691a87-7962-4fa9-ba52-7cc466ecd982",
            "08ec927c-18e6-4bba-837a-b16de7061580",
        ]

    def test_resolve_choice_reorder__id指定で対象を指定順に解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_choice_reorder(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_ids=[
                "74691a87-7962-4fa9-ba52-7cc466ecd982",
                "08ec927c-18e6-4bba-837a-b16de7061580",
            ],
            choice_name_ens=None,
        )

        assert actual.target_attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"
        assert [choice["choice_id"] for choice in actual.first_choices] == [
            "74691a87-7962-4fa9-ba52-7cc466ecd982",
            "08ec927c-18e6-4bba-837a-b16de7061580",
        ]

    def test_resolve_choice_reorder__選択肢系でない属性ならエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_choice_reorder(
                annotation_specs,
                attribute_id=None,
                attribute_name_en="comment",
                choice_ids=None,
                choice_name_ens=["small"],
            )

    def test_resolve_choice_reorder__存在しない選択肢ならエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_choice_reorder(
                annotation_specs,
                attribute_id=None,
                attribute_name_en="type",
                choice_ids=None,
                choice_name_ens=["not-found"],
            )


class TestValidateChoiceReorderInputs:
    def test_validate_choice_reorder_inputs__attributeのidとnameを同時指定したらエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_reorder_inputs(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en="type",
                choice_ids=["74691a87-7962-4fa9-ba52-7cc466ecd982"],
                choice_name_ens=None,
            )

    def test_validate_choice_reorder_inputs__choiceのidとnameを同時指定したらエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_reorder_inputs(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_ids=["74691a87-7962-4fa9-ba52-7cc466ecd982"],
                choice_name_ens=["small"],
            )

    def test_validate_choice_reorder_inputs__選択肢指定なしならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_reorder_inputs(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_ids=[],
                choice_name_ens=None,
            )

    def test_validate_choice_reorder_inputs__重複したidならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_reorder_inputs(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_ids=["74691a87-7962-4fa9-ba52-7cc466ecd982", "74691a87-7962-4fa9-ba52-7cc466ecd982"],
                choice_name_ens=None,
            )

    def test_validate_choice_reorder_inputs__重複したnameならエラー(self) -> None:
        with pytest.raises(ValueError):
            validate_choice_reorder_inputs(
                attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
                attribute_name_en=None,
                choice_ids=None,
                choice_name_ens=["small", "small"],
            )


class TestMessage:
    def test_create_comment_for_reorder_choices(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small", "large"],
        )

        actual = create_comment_for_reorder_choices(resolved)

        assert "以下の属性の選択肢を指定順で先頭に移動しました。" in actual
        assert "対象属性: type" in actual
        assert "対象選択肢: small, large" in actual

    def test_create_confirm_message_for_reorder_choices(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small", "large"],
        )

        actual = create_confirm_message_for_reorder_choices(resolved)

        assert "属性 'type' の選択肢(2件)を指定順で先頭に移動します。" in actual
        assert "指定しなかった選択肢は現在の順番を維持します。" in actual
        assert actual.endswith("よろしいですか？")


class TestBuildRequestBodyForReorderChoices:
    def test_build_request_body_for_reorder_choices__指定選択肢を対象属性内の先頭に移動する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small", "large"],
        )

        actual = build_request_body_for_reorder_choices(annotation_specs, resolved_reorder=resolved, comment=None)

        type_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32")
        assert [choice["choice_id"] for choice in type_attribute["choices"]] == [
            "74691a87-7962-4fa9-ba52-7cc466ecd982",
            "08ec927c-18e6-4bba-837a-b16de7061580",
            "b690fa1a-7b3d-4181-95d8-f5c75927c3fc",
        ]
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下の属性の選択肢を指定順で先頭に移動しました。" in actual["comment"]

    def test_build_request_body_for_reorder_choices__対象外属性は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        other_attribute = copy.deepcopy(next(attribute for attribute in annotation_specs["additionals"] if attribute["additional_data_definition_id"] == "71620647-98cf-48ad-b43b-4af425a24f32"))
        other_attribute["additional_data_definition_id"] = "other_attribute_id"
        annotation_specs["additionals"].append(other_attribute)
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id="71620647-98cf-48ad-b43b-4af425a24f32",
            attribute_name_en=None,
            choice_ids=None,
            choice_name_ens=["small"],
        )

        actual = build_request_body_for_reorder_choices(annotation_specs, resolved_reorder=resolved, comment=None)

        actual_other_attribute = next(attribute for attribute in actual["additionals"] if attribute["additional_data_definition_id"] == "other_attribute_id")
        assert [choice["choice_id"] for choice in actual_other_attribute["choices"]] == [
            "08ec927c-18e6-4bba-837a-b16de7061580",
            "b690fa1a-7b3d-4181-95d8-f5c75927c3fc",
            "74691a87-7962-4fa9-ba52-7cc466ecd982",
        ]

    def test_build_request_body_for_reorder_choices__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small"],
        )

        actual = build_request_body_for_reorder_choices(annotation_specs, resolved_reorder=resolved, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_reorder_choices__元のアノテーション仕様は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved = resolve_choice_reorder(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["small"],
        )

        build_request_body_for_reorder_choices(annotation_specs, resolved_reorder=resolved, comment=None)

        assert annotation_specs == old_annotation_specs
