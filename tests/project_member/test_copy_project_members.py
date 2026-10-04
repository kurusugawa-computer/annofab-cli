from argparse import Namespace
from unittest.mock import Mock

from annofabcli.project_member.copy_project_members import CopyProjectMembers


def test_copy_project_members_deletes_destination_members_when_source_is_empty(monkeypatch):
    command = object.__new__(CopyProjectMembers)
    command.args = Namespace()
    command.service = Mock()
    command.service.wrapper.get_all_project_members.side_effect = [
        [],
        [{"user_id": "user1", "username": "User One", "account_id": "account1", "member_role": "worker", "updated_datetime": "updated"}],
    ]
    command.facade = Mock()
    command.facade.get_organization_name_from_project_id.return_value = "org"
    command.src_project_title = "source"
    command.dest_project_title = "destination"
    monkeypatch.setattr(command, "require_access_to_projects", Mock())
    monkeypatch.setattr(command, "get_organization_members_from_project_id", lambda _: [{"account_id": "account1"}])
    monkeypatch.setattr(command, "confirm_processing", Mock(return_value=True))
    apply_project_members = Mock()
    monkeypatch.setattr(command, "apply_project_members", apply_project_members)

    command.copy_project_members("source_id", "destination_id", delete_dest=True)

    apply_project_members.assert_called_once()
    assert apply_project_members.call_args.args[1][0]["member_status"] == "inactive"


def test_copy_project_members_does_not_deactivate_login_user(monkeypatch):
    command = object.__new__(CopyProjectMembers)
    command.service = Mock()
    command.service.api.login_user_id = "myself"
    command.service.wrapper.get_all_project_members.side_effect = [
        [],
        [
            {"user_id": "myself", "username": "Me", "account_id": "account1", "member_role": "owner", "updated_datetime": "updated"},
            {"user_id": "user1", "username": "User One", "account_id": "account2", "member_role": "worker", "updated_datetime": "updated"},
        ],
    ]
    command.facade = Mock()
    command.src_project_title = "source"
    command.dest_project_title = "destination"
    monkeypatch.setattr(command, "require_access_to_projects", Mock())
    monkeypatch.setattr(command, "get_organization_members_from_project_id", lambda _: [])
    monkeypatch.setattr(command, "confirm_processing", Mock(return_value=True))
    apply_project_members = Mock()
    monkeypatch.setattr(command, "apply_project_members", apply_project_members)

    command.copy_project_members("source_id", "destination_id", delete_dest=True)

    assert [member["user_id"] for member in apply_project_members.call_args.args[1]] == ["user1"]


def test_copy_project_members_does_not_update_login_user(monkeypatch):
    command = object.__new__(CopyProjectMembers)
    command.service = Mock()
    command.service.api.login_user_id = "myself"
    command.service.wrapper.get_all_project_members.side_effect = [
        [{"user_id": "myself", "username": "Me", "account_id": "account1", "member_role": "worker", "member_status": "active"}],
        [],
    ]
    command.facade = Mock()
    command.src_project_title = "source"
    command.dest_project_title = "destination"
    monkeypatch.setattr(command, "require_access_to_projects", Mock())
    monkeypatch.setattr(command, "get_organization_members_from_project_id", lambda _: [{"account_id": "account1"}])
    apply_project_members = Mock()
    monkeypatch.setattr(command, "apply_project_members", apply_project_members)

    command.copy_project_members("source_id", "destination_id")

    apply_project_members.assert_not_called()
