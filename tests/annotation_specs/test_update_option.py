from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock

import annofabapi
import pytest
from annofabapi.models import InputDataType

from annofabcli.annotation_specs.update_option import UpdateOptionMain, build_request_body_for_update_option, read_option_json


@pytest.mark.parametrize("value", [True, False])
def test_read_option_json(*, value: bool) -> None:
    assert read_option_json(json.dumps({"can_overwrap": value})) == {"can_overwrap": value}


def test_read_option_json_file(tmp_path) -> None:
    path = tmp_path / "option.json"
    path.write_text('{"can_overwrap": false}', encoding="utf-8")
    assert read_option_json(f"file://{path}") == {"can_overwrap": False}


@pytest.mark.parametrize("option", [{}, {"unknown": True}, {"can_overwrap": False, "unknown": True}, {"option": {"can_overwrap": True}}])
def test_read_option_json_invalid_keys(option) -> None:
    with pytest.raises(ValueError):
        read_option_json(json.dumps(option))


@pytest.mark.parametrize("option", [None, [], True, "true", 1, {"can_overwrap": None}, {"can_overwrap": "false"}, {"can_overwrap": 0}, {"can_overwrap": 1}])
def test_read_option_json_invalid_type(option) -> None:
    with pytest.raises(TypeError):
        read_option_json(json.dumps(option))


def test_read_option_json_malformed() -> None:
    with pytest.raises(json.JSONDecodeError):
        read_option_json('{"can_overwrap": False}')


@pytest.fixture
def annotation_specs() -> dict:
    return {
        "option": {"can_overwrap": True, "future_option": {"value": 1}},
        "labels": [{"label_id": "label1"}],
        "additionals": [{"additional_data_definition_id": "attribute1"}],
        "restrictions": [],
        "comment": "以前のコメント",
        "updated_datetime": "2026-10-06T00:00:00+09:00",
    }


@pytest.mark.parametrize("comment", [None, "区間の重なりを禁止する", ""])
def test_build_request_body_preserves_other_fields(annotation_specs: dict, comment: str | None) -> None:
    original = copy.deepcopy(annotation_specs)
    actual = build_request_body_for_update_option(annotation_specs, option={"can_overwrap": False}, comment=comment)
    expected = copy.deepcopy(original)
    expected["option"]["can_overwrap"] = False
    expected["comment"] = comment if comment is not None else 'アノテーション仕様のoptionを更新しました。\n{"can_overwrap": false}'
    expected["last_updated_datetime"] = original["updated_datetime"]
    assert actual == expected
    actual["labels"][0]["label_id"] = "changed"
    actual["option"]["future_option"]["value"] = 2
    assert annotation_specs == original


@pytest.fixture
def service(annotation_specs: dict) -> MagicMock:
    service = MagicMock(spec=annofabapi.Resource)
    service.api = MagicMock(spec=annofabapi.AnnofabApi)
    service.api.get_project.return_value = ({"input_data_type": InputDataType.MOVIE.value}, None)
    service.api.get_annotation_specs.return_value = (annotation_specs, None)
    return service


@pytest.mark.parametrize("value", [True, False])
def test_update_option_sends_preserved_specs(service: MagicMock, annotation_specs: dict, *, value: bool) -> None:
    annotation_specs["option"]["can_overwrap"] = not value
    obj = UpdateOptionMain(service, project_id="project1", all_yes=True)
    assert obj.update_option(option={"can_overwrap": value}, comment="変更コメント")
    expected = build_request_body_for_update_option(annotation_specs, option={"can_overwrap": value}, comment="変更コメント")
    service.api.put_annotation_specs.assert_called_once_with("project1", query_params={"v": "3"}, request_body=expected)


@pytest.mark.parametrize("value", [True, False])
def test_update_option_unchanged_skips_write(service: MagicMock, annotation_specs: dict, *, value: bool) -> None:
    annotation_specs["option"]["can_overwrap"] = value
    obj = UpdateOptionMain(service, project_id="project1", all_yes=True)
    assert not obj.update_option(option={"can_overwrap": value})
    service.api.put_annotation_specs.assert_not_called()


@pytest.mark.parametrize("input_data_type", [InputDataType.IMAGE.value, InputDataType.CUSTOM.value])
def test_update_option_non_movie_rejected(service: MagicMock, input_data_type: str) -> None:
    service.api.get_project.return_value = ({"input_data_type": input_data_type}, None)
    obj = UpdateOptionMain(service, project_id="project1", all_yes=True)
    with pytest.raises(ValueError):
        obj.update_option(option={"can_overwrap": False})
    service.api.put_annotation_specs.assert_not_called()


@pytest.mark.parametrize("answer", ["n", "y"])
def test_update_option_confirmation(service: MagicMock, monkeypatch, answer: str) -> None:
    prompts = []

    def respond(prompt: str) -> str:
        prompts.append(prompt)
        return answer

    monkeypatch.setattr("builtins.input", respond)
    obj = UpdateOptionMain(service, project_id="project1", all_yes=False)
    assert obj.update_option(option={"can_overwrap": False}) == (answer == "y")
    assert "can_overwrap: true → false" in prompts[0]
    assert service.api.put_annotation_specs.call_count == (1 if answer == "y" else 0)


def test_update_option_missing_option_key(service: MagicMock, annotation_specs: dict) -> None:
    del annotation_specs["option"]["can_overwrap"]
    obj = UpdateOptionMain(service, project_id="project1", all_yes=True)
    assert obj.update_option(option={"can_overwrap": False})
    assert service.api.put_annotation_specs.call_args.kwargs["request_body"]["option"] == {"can_overwrap": False, "future_option": {"value": 1}}


def test_update_option_api_error_propagates(service: MagicMock) -> None:
    service.api.put_annotation_specs.side_effect = RuntimeError("APIエラー")
    obj = UpdateOptionMain(service, project_id="project1", all_yes=True)
    with pytest.raises(RuntimeError):
        obj.update_option(option={"can_overwrap": False})
