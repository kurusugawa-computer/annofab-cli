from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from annofabcli.annotation_specs.delete_attribute_restriction import (
    DeleteAttributeRestrictionMain,
    create_comment_for_delete_attribute_restriction,
    create_confirm_message_for_delete_attribute_restriction,
    matches_restriction_type,
)

DATA_DIR = Path("./tests/data/annotation_specs")


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


class TestDeleteAttributeRestrictionMain:
    def test_delete_restrictions_by_json(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        restrictions = [
            copy.deepcopy(annotation_specs["restrictions"][1]),
            copy.deepcopy(annotation_specs["restrictions"][4]),
        ]

        result = main.delete_restrictions_by_json(restrictions)

        assert result is True
        assert service.api.last_put is not None
        assert restrictions[0] not in service.api.last_put["restrictions"]
        assert restrictions[1] not in service.api.last_put["restrictions"]
        assert service.api.last_put["comment"] == "以下の属性制約を削除しました。\n'comment' DOES NOT EQUAL ''\n'comment' MATCHES '[abc]+'"

    def test_delete_restrictions_by_json__存在しない制約はスキップする(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        restrictions = [
            {
                "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
                "condition": {"value": "not-found", "_type": "Equals"},
            }
        ]

        result = main.delete_restrictions_by_json(restrictions)

        assert result is False
        assert service.api.last_put is None

    def test_delete_restrictions_by_json__入力内の重複は1回だけ削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        restriction = copy.deepcopy(annotation_specs["restrictions"][1])

        result = main.delete_restrictions_by_json([restriction, copy.deepcopy(restriction)])

        assert result is True
        assert service.api.last_put is not None
        assert service.api.last_put["restrictions"].count(restriction) == 0

    def test_delete_restrictions_by_attribute__attribute_name_en(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.delete_restrictions_by_attribute(
            attribute_ids=None,
            attribute_name_ens=["comment"],
        )

        assert result is True
        assert service.api.last_put is not None
        remaining_comment_restrictions = [restriction for restriction in service.api.last_put["restrictions"] if restriction["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert remaining_comment_restrictions == []
        assert service.api.last_put["comment"] == (
            "以下の属性制約を削除しました。\n"
            "'comment' CAN NOT INPUT\n"
            "'comment' DOES NOT EQUAL ''\n"
            "'comment' EQUALS 'foo'\n"
            "'comment' DOES NOT EQUAL 'bar'\n"
            "'comment' MATCHES '[abc]+'\n"
            "'comment' DOES NOT MATCH '[0-9]+'\n"
            "'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'"
        )

    def test_delete_restrictions_by_attribute__restriction_typeを指定したときは一致する種類だけ削除する(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.delete_restrictions_by_attribute(
            attribute_ids=None,
            attribute_name_ens=["comment"],
            restriction_type="imply",
        )

        assert result is True
        assert service.api.last_put is not None
        remaining_comment_restrictions = [restriction for restriction in service.api.last_put["restrictions"] if restriction["additional_data_definition_id"] == "54fa5e97-6f88-49a4-aeb0-a91a15d11528"]
        assert [restriction["condition"]["_type"] for restriction in remaining_comment_restrictions] == [
            "CanInput",
            "NotEquals",
            "Equals",
            "NotEquals",
            "Matches",
            "NotMatches",
        ]
        assert service.api.last_put["comment"] == "以下の属性制約を削除しました。\n'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'"

    def test_delete_restrictions_by_attribute__対象の制約がないときは更新しない(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.delete_restrictions_by_attribute(
            attribute_ids=None,
            attribute_name_ens=["unclear"],
        )

        assert result is False
        assert service.api.last_put is None

    def test_delete_restrictions_by_attribute__restriction_typeに一致する制約がないときは更新しない(self) -> None:
        annotation_specs = load_annotation_specs()
        service = DummyService(annotation_specs)
        main = DeleteAttributeRestrictionMain(service, project_id="prj1", all_yes=True)  # type: ignore[arg-type]

        result = main.delete_restrictions_by_attribute(
            attribute_ids=None,
            attribute_name_ens=["unclear"],
            restriction_type="imply",
        )

        assert result is False
        assert service.api.last_put is None
