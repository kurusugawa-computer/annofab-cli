from argparse import Namespace
from unittest.mock import Mock

import pytest
import requests
from annofabapi.models import ProjectMember

from annofabcli.project_member.sync_project_members import SyncProjectMembers


def member(user_id: str, role: str = "worker", rate: int | None = None, status: str = "active") -> ProjectMember:
    return {
        "user_id": user_id,
        "account_id": user_id,
        "member_role": role,
        "sampling_inspection_rate": rate,
        "sampling_acceptance_rate": None,
        "member_status": status,
        "updated_datetime": f"updated-{user_id}",
    }


@pytest.fixture
def service():
    result = Mock()
    result.api.login_user_id = "myself"
    result.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: {
        "src": [member("myself", "worker"), member("same"), member("new"), member("changed", rate=None), member("reactivate"), member("outside")],
        "dest": [member("myself", "owner"), member("same"), member("changed", rate=10), member("reactivate", status="inactive"), member("extra")],
    }[project_id]
    result.wrapper.get_all_organization_members.return_value = [{"account_id": user_id} for user_id in ("myself", "same", "new", "changed", "reactivate", "extra")]
    return result


@pytest.mark.parametrize("delete_extra_members", [False, True])
def test_sync_applies_only_eligible_changes(service, delete_extra_members):
    command = SyncProjectMembers(service, Mock(), Namespace(yes=True))
    command.sync_project_members("src", "dest", delete_extra_members=delete_extra_members)
    requests_by_user = {call.args[1]: call.kwargs["request_body"] for call in service.api.put_project_member.call_args_list}
    assert set(requests_by_user) == {"changed", "new", "reactivate"} | ({"extra"} if delete_extra_members else set())
    assert requests_by_user["changed"]["sampling_inspection_rate"] is None
    assert requests_by_user["new"]["last_updated_datetime"] is None
    assert requests_by_user["reactivate"]["last_updated_datetime"] == "updated-reactivate"
    assert requests_by_user["reactivate"]["member_status"] == "active"
    if delete_extra_members:
        assert requests_by_user["extra"]["member_status"] == "inactive"


def test_sync_does_not_write_without_confirmation(service, monkeypatch):
    monkeypatch.setattr("annofabcli.common.cli.prompt_yesnoall", lambda _: (False, False))
    SyncProjectMembers(service, Mock(), Namespace(yes=False)).sync_project_members("src", "dest", delete_extra_members=True)
    service.api.put_project_member.assert_not_called()


def test_sync_continues_after_member_failure(service):
    service.api.put_project_member.side_effect = [requests.HTTPError(), ({}, None), ({}, None)]
    SyncProjectMembers(service, Mock(), Namespace(yes=True)).sync_project_members("src", "dest")
    assert service.api.put_project_member.call_count == 3


def test_sync_empty_source_deletes_only_other_active_members(service):
    service.wrapper.get_all_project_members.side_effect = [[], [member("myself"), member("extra"), member("inactive", status="inactive")]]
    SyncProjectMembers(service, Mock(), Namespace(yes=True)).sync_project_members("src", "dest", delete_extra_members=True)
    assert [call.args[1] for call in service.api.put_project_member.call_args_list] == ["extra"]


def test_sync_handles_multiple_destinations_and_duplicates(service):
    service.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: [member("new")] if project_id == "src" else []
    command = SyncProjectMembers(service, Mock(), Namespace(yes=True, src_project_id="src", dest_project_id=["dest1", "dest2", "dest1"], delete_extra_members=False))
    command.main()
    assert [call.args[:2] for call in service.api.put_project_member.call_args_list] == [("dest1", "new"), ("dest2", "new")]


def test_sync_same_project_makes_no_changes(service):
    SyncProjectMembers(service, Mock(), Namespace(yes=True)).sync_project_members("src", "src", delete_extra_members=True)
    service.api.put_project_member.assert_not_called()


def test_sync_skips_users_outside_destination_organization(service):
    service.wrapper.get_all_project_members.side_effect = [[member("new")], []]
    service.wrapper.get_all_organization_members.side_effect = [[{"account_id": "new"}], []]
    SyncProjectMembers(service, Mock(), Namespace(yes=True)).sync_project_members("src", "dest")
    service.api.put_project_member.assert_not_called()


def test_sync_does_not_add_inactive_source_members(service):
    service.wrapper.get_all_project_members.side_effect = [[member("new", status="inactive")], []]
    SyncProjectMembers(service, Mock(), Namespace(yes=True)).sync_project_members("src", "dest")
    service.api.put_project_member.assert_not_called()
