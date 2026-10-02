from unittest.mock import Mock

from annofabapi.models import ProjectMemberRole

from annofabcli.project_member.invite_project_members import InviteProjectMembersMain


def test_invite_project_members_skips_existing_member():
    command = object.__new__(InviteProjectMembersMain)
    service = Mock()
    command.service = service
    facade = Mock()
    command.facade = facade
    service.wrapper.get_all_project_members.return_value = [{"user_id": "existing", "member_role": "owner"}]
    facade.get_project_title.return_value = "project"

    command.invite_project_members("project_id", ["existing", "new"], ProjectMemberRole.WORKER)

    service.api.put_project_member.assert_called_once()
    assert service.api.put_project_member.call_args.args[:2] == ("project_id", "new")
