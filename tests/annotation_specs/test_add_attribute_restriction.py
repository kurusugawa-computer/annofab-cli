from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from annofabcli.annotation_specs.add_attribute_restriction import AddAttributeRestrictionMain

data_dir = Path("./tests/data/annotation_specs")


class DummyApi:
    def __init__(self, annotation_specs: dict[str, Any]) -> None:
        self.annotation_specs = copy.deepcopy(annotation_specs)
        self.last_put: dict[str, Any] | None = None

    def get_annotation_specs(self, project_id: str, query_params: dict[str, Any]) -> tuple[dict[str, Any], None]:
        assert project_id == "prj1"
        assert query_params == {"v": "3"}
        return copy.deepcopy(self.annotation_specs), None

    def put_annotation_specs(self, project_id: str, query_params: dict[str, Any], request_body: dict[str, Any]) -> None:
        assert project_id == "prj1"
        assert query_params == {"v": "3"}
        self.last_put = request_body


class DummyService:
    def __init__(self, annotation_specs: dict[str, Any]) -> None:
        self.api = DummyApi(annotation_specs)


def load_annotation_specs() -> dict[str, Any]:
    with (data_dir / "annotation_specs.json").open(encoding="utf-8") as f:
        annotation_specs = json.load(f)
    annotation_specs["updated_datetime"] = "2026-04-24T00:00:00+09:00"
    return annotation_specs


class TestAddAttributeRestrictionMain:
    def test_add_restrictions__既存制約と新規制約が混在しても新規制約だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])
        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        result = main.add_restrictions([existing_restriction, new_restriction])

        assert result is True
        assert service.api.last_put is not None
        assert service.api.last_put["restrictions"] == [*annotation_specs["restrictions"], new_restriction]

    def test_add_restrictions__入力内の重複制約は1件だけ追加する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        new_restriction = {
            "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
            "condition": {"value": "bar", "_type": "Equals"},
        }

        result = main.add_restrictions([new_restriction, copy.deepcopy(new_restriction)])

        assert result is True
        assert service.api.last_put is not None
        assert service.api.last_put["restrictions"] == [*annotation_specs["restrictions"], new_restriction]

    def test_add_restrictions__既存制約だけなら更新しない(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = AddAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        existing_restriction = copy.deepcopy(annotation_specs["restrictions"][0])

        result = main.add_restrictions([existing_restriction])

        assert result is False
        assert service.api.last_put is None
