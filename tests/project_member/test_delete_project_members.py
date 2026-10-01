from unittest.mock import Mock

from annofabapi.models import ProjectMemberStatus

from annofabcli.project_member.delete_project_members import DeleteProjectMembersMain


def test_delete_project_members_asks_before_deactivating_user(monkeypatch):
    command = object.__new__(DeleteProjectMembersMain)
    command.service = Mock()
    command.service.wrapper.get_all_project_members.return_value = [
        {
            "user_id": "user1",
            "member_status": ProjectMemberStatus.ACTIVE.value,
            "member_role": "worker",
            "updated_datetime": "updated",
        }
    ]
    command.facade = Mock()
    command.facade.get_project_title.return_value = "project"
    confirm_processing = Mock(return_value=False)
    monkeypatch.setattr(command, "confirm_processing", confirm_processing)

    command.delete_project_members("project_id", ["user1"])

    confirm_processing.assert_called_once()
    command.service.api.put_project_member.assert_not_called()
