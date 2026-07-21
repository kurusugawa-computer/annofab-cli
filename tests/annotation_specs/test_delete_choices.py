from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from annofabcli.annotation_specs.delete_choices import (
    AffectingAnnotation,
    DeleteChoicesMain,
    build_request_body_for_delete_choices,
    create_comment_for_delete_choices,
    create_confirm_message_for_delete_choices,
    resolve_choice_deletion,
    restriction_references_choice,
)

DATA_DIR = Path("./tests/data/annotation_specs")
TYPE_ATTRIBUTE_ID = "71620647-98cf-48ad-b43b-4af425a24f32"
LARGE_CHOICE_ID = "08ec927c-18e6-4bba-837a-b16de7061580"
MEDIUM_CHOICE_ID = "b690fa1a-7b3d-4181-95d8-f5c75927c3fc"
SMALL_CHOICE_ID = "74691a87-7962-4fa9-ba52-7cc466ecd982"


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


def get_type_attribute(annotation_specs: dict[str, Any]) -> dict[str, Any]:
    return next(attribute for attribute in annotation_specs["additionals"] if attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID)


class TestDeleteChoicesHelpers:
    def test_restriction_references_choice__equalsを検出する(self) -> None:
        annotation_specs = load_annotation_specs()
        restriction = annotation_specs["restrictions"][-3]

        assert restriction_references_choice(restriction, attribute_id=TYPE_ATTRIBUTE_ID, choice_ids={MEDIUM_CHOICE_ID}) is True
        assert restriction_references_choice(restriction, attribute_id=TYPE_ATTRIBUTE_ID, choice_ids={LARGE_CHOICE_ID}) is False

    def test_restriction_references_choice__matchesのvalueは選択肢参照として扱わない(self) -> None:
        restriction = {
            "additional_data_definition_id": TYPE_ATTRIBUTE_ID,
            "condition": {
                "value": MEDIUM_CHOICE_ID,
                "_type": "Matches",
            },
        }

        assert restriction_references_choice(restriction, attribute_id=TYPE_ATTRIBUTE_ID, choice_ids={MEDIUM_CHOICE_ID}) is False

    def test_create_comment_for_delete_choices(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        actual = create_comment_for_delete_choices(resolved)

        assert "以下の選択肢を属性から削除しました。" in actual
        assert "attribute_name_en='type', choice_name_en='medium'" in actual
        assert "'type' EQUALS 'medium'" in actual

    def test_create_confirm_message_for_delete_choices(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        actual = create_confirm_message_for_delete_choices(resolved, affecting_annotations=[])

        assert "以下の選択肢(1件)を属性から削除します。" in actual
        assert "attribute_name_en='type', choice_name_en='medium'" in actual
        assert actual.endswith("よろしいですか？")


class TestResolveChoiceDeletion:
    def test_resolve_choice_deletion__choice_name_enで対象を解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        assert actual.target_attribute["additional_data_definition_id"] == TYPE_ATTRIBUTE_ID
        assert [choice["choice_id"] for choice in actual.choices_to_remove] == [MEDIUM_CHOICE_ID]
        assert actual.restriction_text_list == ["'type' EQUALS 'medium'"]

    def test_resolve_choice_deletion__choice_idで対象を解決する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_choice_deletion(
            annotation_specs,
            attribute_id=TYPE_ATTRIBUTE_ID,
            attribute_name_en=None,
            choice_ids=[LARGE_CHOICE_ID],
            choice_name_ens=None,
        )

        assert [choice["choice_id"] for choice in actual.choices_to_remove] == [LARGE_CHOICE_ID]

    def test_resolve_choice_deletion__選択肢系属性でないときはエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_choice_deletion(
                annotation_specs,
                attribute_id="54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                attribute_name_en=None,
                choice_ids=[LARGE_CHOICE_ID],
                choice_name_ens=None,
            )

    def test_resolve_choice_deletion__削除後の選択肢数が2件未満になるときはエラー(self) -> None:
        annotation_specs = load_annotation_specs()

        with pytest.raises(ValueError):
            resolve_choice_deletion(
                annotation_specs,
                attribute_id=TYPE_ATTRIBUTE_ID,
                attribute_name_en=None,
                choice_ids=[MEDIUM_CHOICE_ID, SMALL_CHOICE_ID],
                choice_name_ens=None,
            )

    def test_resolve_choice_deletion__defaultを削除するときはunsafe_defaultsが必要(self) -> None:
        annotation_specs = load_annotation_specs()
        get_type_attribute(annotation_specs)["default"] = LARGE_CHOICE_ID

        with pytest.raises(ValueError):
            resolve_choice_deletion(
                annotation_specs,
                attribute_id=TYPE_ATTRIBUTE_ID,
                attribute_name_en=None,
                choice_ids=[LARGE_CHOICE_ID],
                choice_name_ens=None,
                unsafe_defaults=False,
            )

    def test_resolve_choice_deletion__unsafe_defaultsならdefaultの削除を許可する(self) -> None:
        annotation_specs = load_annotation_specs()
        get_type_attribute(annotation_specs)["default"] = LARGE_CHOICE_ID

        actual = resolve_choice_deletion(
            annotation_specs,
            attribute_id=TYPE_ATTRIBUTE_ID,
            attribute_name_en=None,
            choice_ids=[LARGE_CHOICE_ID],
            choice_name_ens=None,
            unsafe_defaults=True,
        )

        assert [choice["choice_id"] for choice in actual.choices_to_remove] == [LARGE_CHOICE_ID]


class TestBuildRequestBodyForDeleteChoices:
    def test_build_request_body_for_delete_choices__関連制約も削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        actual = build_request_body_for_delete_choices(annotation_specs, resolved_deletion=resolved, unsafe_defaults=False, comment=None)

        updated_attribute = get_type_attribute(actual)
        assert [choice["choice_id"] for choice in updated_attribute["choices"]] == [LARGE_CHOICE_ID, SMALL_CHOICE_ID]
        assert all(not restriction_references_choice(restriction, attribute_id=TYPE_ATTRIBUTE_ID, choice_ids={MEDIUM_CHOICE_ID}) for restriction in actual["restrictions"])
        assert actual["last_updated_datetime"] == "2026-04-24T00:00:00+09:00"
        assert "以下の選択肢を属性から削除しました。" in actual["comment"]

    def test_build_request_body_for_delete_choices__unsafe_defaultsならdefaultを解除する(self) -> None:
        annotation_specs = load_annotation_specs()
        get_type_attribute(annotation_specs)["default"] = LARGE_CHOICE_ID
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=TYPE_ATTRIBUTE_ID,
            attribute_name_en=None,
            choice_ids=[LARGE_CHOICE_ID],
            choice_name_ens=None,
            unsafe_defaults=True,
        )

        actual = build_request_body_for_delete_choices(annotation_specs, resolved_deletion=resolved, unsafe_defaults=True, comment=None)

        assert get_type_attribute(actual)["default"] == ""

    def test_build_request_body_for_delete_choices__custom_comment(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        actual = build_request_body_for_delete_choices(annotation_specs, resolved_deletion=resolved, unsafe_defaults=False, comment="custom")

        assert actual["comment"] == "custom"

    def test_build_request_body_for_delete_choices__元のアノテーション仕様は変更しない(self) -> None:
        annotation_specs = load_annotation_specs()
        old_annotation_specs = copy.deepcopy(annotation_specs)
        resolved = resolve_choice_deletion(
            annotation_specs,
            attribute_id=None,
            attribute_name_en="type",
            choice_ids=None,
            choice_name_ens=["medium"],
        )

        build_request_body_for_delete_choices(annotation_specs, resolved_deletion=resolved, unsafe_defaults=False, comment=None)

        assert annotation_specs == old_annotation_specs


class TestDeleteChoicesMain:
    def test_validate_deletion__既存アノテーションに影響するときは許可オプションを案内する(self, caplog: pytest.LogCaptureFixture) -> None:
        obj = DeleteChoicesMain(
            service=None,  # type: ignore[arg-type]
            project_id="project_id",
            all_yes=True,
            allow_affecting_annotations=False,
        )

        with caplog.at_level(logging.WARNING):
            actual = obj.validate_deletion(
                [
                    AffectingAnnotation(
                        attribute_name_en="type",
                        choice_name_en="medium",
                        annotation_count=3,
                    )
                ]
            )

        assert actual is False
        assert "--allow_affecting_annotations" in caplog.text
