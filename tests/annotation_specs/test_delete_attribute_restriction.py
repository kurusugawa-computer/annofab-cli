from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from annofabcli.annotation_specs.delete_attribute_restriction import (
    build_request_body_for_delete_attribute_restriction,
    create_comment_for_delete_attribute_restriction,
    create_confirm_message_for_delete_attribute_restriction,
    resolve_restrictions_to_delete_by_attribute,
    resolve_restrictions_to_delete_by_json,
)
from annofabcli.annotation_specs.restriction_type import matches_restriction_type

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestDeleteAttributeRestrictionHelpers:
    def test_create_comment_for_delete_attribute_restriction(self) -> None:
        actual = create_comment_for_delete_attribute_restriction(["'comment' DOES NOT EQUAL ''", "'link' HAS LABEL 'bike'"])
        assert actual == "以下の属性制約を削除しました。\n'comment' DOES NOT EQUAL ''\n'link' HAS LABEL 'bike'"

    def test_create_confirm_message_for_delete_attribute_restriction(self) -> None:
        actual = create_confirm_message_for_delete_attribute_restriction(["'comment' DOES NOT EQUAL ''", "'link' HAS LABEL 'bike'"])
        assert actual == "以下の属性制約(2件)を削除します。よろしいですか？\n * 'comment' DOES NOT EQUAL ''\n * 'link' HAS LABEL 'bike'"

    def test_matches_restriction_type(self) -> None:
        restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"_type": "Imply"},
        }

        assert matches_restriction_type(restriction, "imply") is True
        assert matches_restriction_type(restriction, "matches") is False
        assert matches_restriction_type(restriction, None) is True


class TestDeleteRestrictionsByJson:
    def test_resolve_restrictions_to_delete_by_json(self) -> None:
        annotation_specs = load_annotation_specs()
        restrictions = [
            copy.deepcopy(annotation_specs["restrictions"][1]),
            copy.deepcopy(annotation_specs["restrictions"][4]),
        ]

        actual = resolve_restrictions_to_delete_by_json(annotation_specs, restrictions)

        assert actual.restrictions_to_remove == restrictions
        assert actual.restriction_text_list == [
            "'comment' DOES NOT EQUAL ''",
            "'comment' MATCHES '[abc]+'",
        ]

    def test_resolve_restrictions_to_delete_by_json__存在しない制約はスキップする(self) -> None:
        annotation_specs = load_annotation_specs()
        restrictions = [
            {
                "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                "condition": {"value": "not-found", "_type": "Equals"},
            }
        ]

        actual = resolve_restrictions_to_delete_by_json(annotation_specs, restrictions)

        assert actual.restrictions_to_remove == []

    def test_resolve_restrictions_to_delete_by_json__入力内の重複は1回だけ削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        restriction = copy.deepcopy(annotation_specs["restrictions"][1])

        actual = resolve_restrictions_to_delete_by_json(annotation_specs, [restriction, copy.deepcopy(restriction)])

        assert actual.restrictions_to_remove == [restriction]

    def test_build_request_body_for_delete_attribute_restriction(self) -> None:
        annotation_specs = load_annotation_specs()
        restrictions = [
            copy.deepcopy(annotation_specs["restrictions"][1]),
            copy.deepcopy(annotation_specs["restrictions"][4]),
        ]
        resolved = resolve_restrictions_to_delete_by_json(annotation_specs, restrictions)

        actual = build_request_body_for_delete_attribute_restriction(
            annotation_specs,
            restrictions_to_remove=resolved.restrictions_to_remove,
            restriction_text_list=resolved.restriction_text_list,
            comment=None,
        )

        assert restrictions[0] not in actual["restrictions"]
        assert restrictions[1] not in actual["restrictions"]
        assert actual["comment"] == "以下の属性制約を削除しました。\n'comment' DOES NOT EQUAL ''\n'comment' MATCHES '[abc]+'"


class TestDeleteRestrictionsByAttribute:
    def test_resolve_restrictions_to_delete_by_attribute__attribute_name_en(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_restrictions_to_delete_by_attribute(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        assert [restriction["condition"]["_type"] for restriction in actual.restrictions_to_remove] == [
            "CanInput",
            "NotEquals",
            "Equals",
            "NotEquals",
            "Matches",
            "NotMatches",
            "Imply",
        ]

    def test_resolve_restrictions_to_delete_by_attribute__restriction_typeを指定したときは一致する種類だけ削除する(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_restrictions_to_delete_by_attribute(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["comment"],
            restriction_type="imply",
        )

        assert [restriction["condition"]["_type"] for restriction in actual.restrictions_to_remove] == ["Imply"]
        assert actual.restriction_text_list == ["'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'"]

    def test_resolve_restrictions_to_delete_by_attribute__対象の制約がないときは空(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_restrictions_to_delete_by_attribute(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
        )

        assert actual.restrictions_to_remove == []

    def test_resolve_restrictions_to_delete_by_attribute__restriction_typeに一致する制約がないときは空(self) -> None:
        annotation_specs = load_annotation_specs()

        actual = resolve_restrictions_to_delete_by_attribute(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            restriction_type="imply",
        )

        assert actual.restrictions_to_remove == []

    def test_build_request_body_for_delete_attribute_restriction__attribute_name_en(self) -> None:
        annotation_specs = load_annotation_specs()
        resolved = resolve_restrictions_to_delete_by_attribute(
            annotation_specs,
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        actual = build_request_body_for_delete_attribute_restriction(
            annotation_specs,
            restrictions_to_remove=resolved.restrictions_to_remove,
            restriction_text_list=resolved.restriction_text_list,
            comment=None,
        )

        remaining_comment_restrictions = [restriction for restriction in actual["restrictions"] if restriction["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert remaining_comment_restrictions == []
        assert actual["comment"] == (
            "以下の属性制約を削除しました。\n"
            "'comment' CAN NOT INPUT\n"
            "'comment' DOES NOT EQUAL ''\n"
            "'comment' EQUALS 'foo'\n"
            "'comment' DOES NOT EQUAL 'bar'\n"
            "'comment' MATCHES '[abc]+'\n"
            "'comment' DOES NOT MATCH '[0-9]+'\n"
            "'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'"
        )
