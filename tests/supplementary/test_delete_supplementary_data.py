from argparse import Namespace

import pytest
import requests
from annofabapi.models import ProjectMemberRole

from annofabcli.common.exceptions import ProjectAuthorizationError
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.supplementary.delete_supplementary_data import DeleteSupplementaryData


def test_deletes_all_children_only_of_selected_input(supplementary_delete_service, tmp_path):
    service = supplementary_delete_service
    ids = tmp_path / "inputs.txt"
    ids.write_text("input1\nmissing-input\n", encoding="utf-8")
    args = Namespace(project_id="project1", input_data_id=[f"file://{ids}"], yes=True)

    DeleteSupplementaryData(service, AnnofabApiFacade(service), args).main()

    assert [(call.kwargs["input_data_id"], call.kwargs["supplementary_data_id"]) for call in service.api.delete_supplementary_data.call_args_list] == [
        ("input1", "s1"),
        ("input1", "s2"),
        ("input1", "keep"),
    ]


def test_confirmation_is_per_input_and_declining_keeps_children(supplementary_delete_service, monkeypatch):
    service = supplementary_delete_service
    prompts = []

    def confirm(message):
        prompts.append(message)
        return "n" if "input1" in message else "y"

    monkeypatch.setattr("builtins.input", confirm)
    args = Namespace(project_id="project1", input_data_id=["input1", "input2"], yes=False)
    DeleteSupplementaryData(service, AnnofabApiFacade(service), args).main()

    assert len(prompts) == 2
    assert [call.kwargs["input_data_id"] for call in service.api.delete_supplementary_data.call_args_list] == ["input2"] * 3


def test_failed_delete_continues_with_other_children(supplementary_delete_service):
    service = supplementary_delete_service
    service.api.delete_supplementary_data.side_effect = [requests.HTTPError(), None, None]
    args = Namespace(project_id="project1", input_data_id=["input1"], yes=True)
    DeleteSupplementaryData(service, AnnofabApiFacade(service), args).main()
    assert [call.kwargs["supplementary_data_id"] for call in service.api.delete_supplementary_data.call_args_list] == ["s1", "s2", "keep"]


def test_requires_owner_before_deleting(supplementary_delete_service):
    service = supplementary_delete_service
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.TRAINING_DATA_USER.value}, None)
    args = Namespace(project_id="project1", input_data_id=["input1"], yes=True)
    with pytest.raises(ProjectAuthorizationError):
        DeleteSupplementaryData(service, AnnofabApiFacade(service), args).main()
    service.api.delete_supplementary_data.assert_not_called()
