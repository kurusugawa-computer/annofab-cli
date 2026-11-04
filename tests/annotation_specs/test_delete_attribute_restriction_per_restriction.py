from __future__ import annotations

import copy
import json
from argparse import Namespace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from annofabcli.annotation_specs.delete_attribute_restriction import build_request_body_for_delete_attribute_restriction
from annofabcli.annotation_specs.delete_attribute_restriction_per_restriction import DeleteAttributeRestrictionPerRestriction, resolve_restrictions_to_delete_by_json

DATA_DIR = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (DATA_DIR / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


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


@pytest.mark.parametrize("from_file", [False, True])
def test_command_deletes_exact_restrictions_only(tmp_path, from_file):
    service = Mock()
    specs = load_annotation_specs()
    original = copy.deepcopy(specs)
    service.api.get_annotation_specs.return_value = (specs, None)
    requested = [copy.deepcopy(specs["restrictions"][1])]
    content = json.dumps(requested)
    path = tmp_path / "restrictions.json"
    path.write_text(content, encoding="utf-8")
    args = Namespace(project_id="project1", restriction_json=f"file://{path}" if from_file else content, comment=None, yes=True)
    DeleteAttributeRestrictionPerRestriction(service, Mock(), args).main()
    body = service.api.put_annotation_specs.call_args.kwargs["request_body"]
    assert body["restrictions"] == [item for item in original["restrictions"] if item not in requested]
    assert body["last_updated_datetime"] == original["updated_datetime"]
    assert body["comment"] == "以下の属性制約を削除しました。\n'comment' DOES NOT EQUAL ''"
    assert specs == original


def test_declining_individual_deletion_keeps_specs(monkeypatch):
    service = Mock()
    specs = load_annotation_specs()
    service.api.get_annotation_specs.return_value = (specs, None)
    monkeypatch.setattr("builtins.input", lambda _message: "n")
    args = Namespace(project_id="project1", restriction_json=json.dumps([specs["restrictions"][1]]), comment=None, yes=False)
    DeleteAttributeRestrictionPerRestriction(service, Mock(), args).main()
    service.api.put_annotation_specs.assert_not_called()


def test_no_matching_restrictions_does_not_update():
    service = Mock()
    service.api.get_annotation_specs.return_value = (load_annotation_specs(), None)
    args = Namespace(project_id="project1", restriction_json="[]", comment=None, yes=True)
    DeleteAttributeRestrictionPerRestriction(service, Mock(), args).main()
    service.api.put_annotation_specs.assert_not_called()


def test_non_array_json_does_not_update():
    service = Mock()
    args = Namespace(project_id="project1", restriction_json="{}", comment=None, yes=True)
    with pytest.raises(SystemExit):
        DeleteAttributeRestrictionPerRestriction(service, Mock(), args).main()
    service.api.put_annotation_specs.assert_not_called()
