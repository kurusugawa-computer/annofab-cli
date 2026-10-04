from argparse import Namespace
from unittest.mock import Mock

import pytest

from annofabcli.project_member.update_project_member_roles import UpdateProjectMemberRoles


@pytest.mark.parametrize("all_users", [False, True])
def test_update_role_changes_multiple_users_and_preserves_rates(all_users):
    service = Mock()
    service.api.login_user_id = "myself"
    service.wrapper.get_all_project_members.return_value = [
        {"user_id": user_id, "member_status": "active", "member_role": "accepter", "sampling_inspection_rate": 30, "sampling_acceptance_rate": 40, "updated_datetime": "updated"}
        for user_id in ["myself", "user1", "user2"]
    ]
    command = UpdateProjectMemberRoles(service, Mock(), Namespace(yes=True, project_id="project", all_users=all_users, user_id=["user1", "user2", "user1"], role="worker"))

    command.main()

    calls = service.api.put_project_member.call_args_list
    assert [call.args[1] for call in calls] == ["user1", "user2"]
    assert all(call.kwargs["request_body"]["member_role"] == "worker" for call in calls)
    assert all(call.kwargs["request_body"]["sampling_inspection_rate"] == 30 for call in calls)
    assert all(call.kwargs["request_body"]["sampling_acceptance_rate"] == 40 for call in calls)
