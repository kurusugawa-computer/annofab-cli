import json
from argparse import Namespace

import pytest
import requests
from annofabapi.models import ProjectMemberRole

from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE
from annofabcli.common.exceptions import ProjectAuthorizationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.supplementary.delete_supplementary_data_per_supplementary_data import DeleteSupplementaryDataPerSupplementaryData


@pytest.mark.parametrize("input_format", ["csv", "json"])
def test_deletes_only_requested_children(supplementary_delete_service, tmp_path, input_format):
    service = supplementary_delete_service
    records = [
        {"input_data_id": "input1", "supplementary_data_id": "s1"},
        {"input_data_id": "input1", "supplementary_data_id": "missing"},
        {"input_data_id": "input2", "supplementary_data_id": "s2"},
        {"input_data_id": "missing-input", "supplementary_data_id": "s1"},
    ]
    path = tmp_path / f"targets.{input_format}"
    if input_format == "csv":
        path.write_text("input_data_id,supplementary_data_id\n" + "\n".join(f"{row['input_data_id']},{row['supplementary_data_id']}" for row in records), encoding="utf-8")
    else:
        path.write_text(json.dumps(records), encoding="utf-8")
    args = Namespace(project_id="project1", csv=path if input_format == "csv" else None, json=f"file://{path}" if input_format == "json" else None, yes=True)

    DeleteSupplementaryDataPerSupplementaryData(service, AnnofabApiFacade(service), args).main()

    assert [(call.kwargs["input_data_id"], call.kwargs["supplementary_data_id"]) for call in service.api.delete_supplementary_data.call_args_list] == [("input1", "s1"), ("input2", "s2")]


def test_confirmation_is_per_supplementary_data(supplementary_delete_service, monkeypatch):
    service = supplementary_delete_service
    prompts = []
    answers = iter(["n", "y"])

    def confirm(message):
        prompts.append(message)
        return next(answers)

    monkeypatch.setattr("builtins.input", confirm)
    records = [{"input_data_id": "input1", "supplementary_data_id": value} for value in ["s1", "s2"]]
    args = Namespace(project_id="project1", csv=None, json=json.dumps(records), yes=False)
    DeleteSupplementaryDataPerSupplementaryData(service, AnnofabApiFacade(service), args).main()
    assert len(prompts) == 2
    assert [call.kwargs["supplementary_data_id"] for call in service.api.delete_supplementary_data.call_args_list] == ["s2"]


def test_failed_delete_continues_with_other_targets(supplementary_delete_service):
    service = supplementary_delete_service
    service.api.delete_supplementary_data.side_effect = [requests.HTTPError(), None]
    records = [{"input_data_id": "input1", "supplementary_data_id": value} for value in ["s1", "s2"]]
    args = Namespace(project_id="project1", csv=None, json=json.dumps(records), yes=True)
    DeleteSupplementaryDataPerSupplementaryData(service, AnnofabApiFacade(service), args).main()
    assert [call.kwargs["supplementary_data_id"] for call in service.api.delete_supplementary_data.call_args_list] == ["s1", "s2"]


def test_requires_owner_before_deleting(supplementary_delete_service):
    service = supplementary_delete_service
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.TRAINING_DATA_USER.value}, None)
    args = Namespace(project_id="project1", csv=None, json='[{"input_data_id":"input1","supplementary_data_id":"s1"}]', yes=True)
    with pytest.raises(ProjectAuthorizationError):
        DeleteSupplementaryDataPerSupplementaryData(service, AnnofabApiFacade(service), args).main()
    service.api.delete_supplementary_data.assert_not_called()


def test_non_array_json_does_not_delete(supplementary_delete_service):
    service = supplementary_delete_service
    args = Namespace(project_id="project1", csv=None, json="{}", yes=True)
    with pytest.raises(SystemExit) as error:
        DeleteSupplementaryDataPerSupplementaryData(service, AnnofabApiFacade(service), args).main()
    assert error.value.code == COMMAND_LINE_ERROR_STATUS_CODE
    service.api.delete_supplementary_data.assert_not_called()
