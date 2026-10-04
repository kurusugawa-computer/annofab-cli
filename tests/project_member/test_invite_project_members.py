from unittest.mock import Mock

from annofabapi.models import ProjectMemberRole

from annofabcli.project_member.invite_project_members import InviteProjectMembersMain


def test_invite_project_members_skips_existing_member():
    command = object.__new__(InviteProjectMembersMain)
    service = Mock()
    command.service = service
    facade = Mock()
    command.facade = facade
    service.wrapper.get_all_project_members.return_value = [{"user_id": "existing", "member_role": "owner", "member_status": "active"}]
    facade.get_project_title.return_value = "project"

    command.invite_project_members("project_id", ["existing", "new"], ProjectMemberRole.WORKER)

    service.api.put_project_member.assert_called_once()
    assert service.api.put_project_member.call_args.args[:2] == ("project_id", "new")
    assert service.api.put_project_member.call_args.kwargs["request_body"]["last_updated_datetime"] is None


def test_invite_project_members_reactivates_inactive_member_with_updated_datetime():
    command = object.__new__(InviteProjectMembersMain)
    service = Mock()
    command.service = service
    command.facade = Mock()
    service.wrapper.get_all_project_members.return_value = [{"user_id": "inactive", "member_role": "accepter", "member_status": "inactive", "updated_datetime": "2026-10-01T12:00:00+09:00"}]

    command.invite_project_members("project_id", ["inactive"], ProjectMemberRole.WORKER)

    service.wrapper.get_all_project_members.assert_called_once_with("project_id", query_params={"include_inactive_member": True})
    service.api.put_project_member.assert_called_once_with(
        "project_id",
        "inactive",
        request_body={"member_status": "active", "member_role": "worker", "last_updated_datetime": "2026-10-01T12:00:00+09:00"},
    )
