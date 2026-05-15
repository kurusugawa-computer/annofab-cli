from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from annofabcli.annotation_specs.add_attribute_restriction import (
    build_request_body_for_add_attribute_restriction,
    resolve_restrictions_to_add,
)

data_dir = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestAddAttributeRestriction:
    def test_resolve_restrictions_to_add__既存制約と新規制約が混在しても新規制約だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])
        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        actual = resolve_restrictions_to_add(annotation_specs, [existing_restriction, new_restriction])

        assert actual.new_restrictions == [new_restriction]

    def test_resolve_restrictions_to_add__入力内の重複制約は1件だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()

        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        actual = resolve_restrictions_to_add(annotation_specs, [new_restriction, copy.deepcopy(new_restriction)])

        assert actual.new_restrictions == [new_restriction]

    def test_resolve_restrictions_to_add__既存制約だけなら空になる(self) -> None:
        annotation_specs = load_annotation_specs()

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])

        actual = resolve_restrictions_to_add(annotation_specs, [existing_restriction])

        assert actual.new_restrictions == []

    def test_build_request_body_for_add_attribute_restriction(self) -> None:
        annotation_specs = load_annotation_specs()
        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }
        resolved = resolve_restrictions_to_add(annotation_specs, [new_restriction])

        actual = build_request_body_for_add_attribute_restriction(
            annotation_specs,
            new_restrictions=resolved.new_restrictions,
            new_restriction_text_list=resolved.new_restriction_text_list,
            comment=None,
        )

        assert actual["restrictions"] == [*annotation_specs["restrictions"], new_restriction]
