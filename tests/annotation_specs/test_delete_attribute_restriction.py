from __future__ import annotations

import copy
import json
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from annofabcli.annotation_specs.delete_attribute_restriction import (
    DeleteAttributeRestriction,
    build_request_body_for_delete_attribute_restriction,
    create_comment_for_delete_attribute_restriction,
    create_confirm_message_for_delete_attribute_restriction,
    resolve_restrictions_to_delete_by_attribute,
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


@pytest.mark.parametrize("selection", ["id", "name"])
@pytest.mark.parametrize("restriction_type", [None, "imply"])
def test_command_deletes_only_matching_attribute_restrictions(selection, restriction_type):
    service = Mock()
    specs = load_annotation_specs()
    original = copy.deepcopy(specs)
    service.api.get_annotation_specs.return_value = (specs, None)
    attribute_id = "54fa5e97-6f88-49a4-aeb0-a91a15d11528"
    args = Namespace(
        project_id="project1",
        attribute_id=[attribute_id] if selection == "id" else None,
        attribute_name_en=["comment"] if selection == "name" else None,
        restriction_type=restriction_type,
        comment="test change",
        yes=True,
    )
    DeleteAttributeRestriction(service, Mock(), args).main()
    body = service.api.put_annotation_specs.call_args.kwargs["request_body"]
    expected = [item for item in original["restrictions"] if not (item["additional_data_definition_id"] == attribute_id and matches_restriction_type(item, restriction_type))]
    assert body["restrictions"] == expected
    assert body["comment"] == "test change"
    assert body["last_updated_datetime"] == original["updated_datetime"]
    assert specs == original


def test_declining_attribute_deletion_keeps_specs(monkeypatch):
    service = Mock()
    service.api.get_annotation_specs.return_value = (load_annotation_specs(), None)
    monkeypatch.setattr("builtins.input", lambda _message: "n")
    args = Namespace(project_id="project1", attribute_id=None, attribute_name_en=["comment"], restriction_type=None, comment=None, yes=False)
    DeleteAttributeRestriction(service, Mock(), args).main()
    service.api.put_annotation_specs.assert_not_called()
