from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from annofabcli.annotation_specs.add_attribute_restriction import AddAttributeRestrictionMain

data_dir = Path("./tests/data/annotation_specs")


def load_annotation_specs() -> dict[str, Any]:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


def create_service_mock(annotation_specs: dict[str, Any]) -> Mock:
    service = Mock()
    service.api = Mock()
    service.api.get_annotation_specs.return_value = (copy.deepcopy(annotation_specs), None)
    return service


class TestAddAttributeRestrictionMain:
    def test_add_restrictions__既存制約と新規制約が混在しても新規制約だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = create_service_mock(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])
        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        result = main.add_restrictions([existing_restriction, new_restriction])

        assert result is True
        request_body = service.api.put_annotation_specs.call_args.kwargs["request_body"]
        assert request_body["restrictions"] == [*annotation_specs["restrictions"], new_restriction]

    def test_add_restrictions__入力内の重複制約は1件だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = create_service_mock(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)

        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        result = main.add_restrictions([new_restriction, copy.deepcopy(new_restriction)])

        assert result is True
        request_body = service.api.put_annotation_specs.call_args.kwargs["request_body"]
        assert request_body["restrictions"] == [*annotation_specs["restrictions"], new_restriction]

    def test_add_restrictions__既存制約だけなら更新しない(self) -> None:
        annotation_specs = load_annotation_specs()
        service = create_service_mock(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])

        result = main.add_restrictions([existing_restriction])

        assert result is False
        service.api.put_annotation_specs.assert_not_called()
