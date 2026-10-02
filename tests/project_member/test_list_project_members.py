from argparse import Namespace
from unittest.mock import Mock

from annofabcli.common.enums import OutputFormat
from annofabcli.project_member.list_users import ListProjectMembers


def test_list_project_members_csv_has_headers_when_empty(monkeypatch):
    command = object.__new__(ListProjectMembers)
    command.args = Namespace(project_id=["project_id"], organization=None, include_inactive=False, parallelism=None, format=OutputFormat.CSV.value)
    monkeypatch.setattr(command, "get_project_members_with_project_id", Mock(return_value=[]))
    print_csv = Mock()
    monkeypatch.setattr(command, "print_csv", print_csv)

    command.main()

    actual_dataframe = print_csv.call_args.args[0]
    assert list(actual_dataframe.columns) == ListProjectMembers.PRIOR_COLUMNS


def test_list_project_members_from_organization(monkeypatch):
    command = object.__new__(ListProjectMembers)
    command.args = Namespace(project_id=None, organization="org", include_inactive=False, parallelism=2, format=OutputFormat.JSON.value)
    command.service = Mock()
    command.service.api.account_id = "account"
    command.service.wrapper.get_all_projects_of_organization.return_value = [{"project_id": "project1"}, {"project_id": "project2"}]
    get_members = Mock(return_value=[{"user_id": "user1"}])
    monkeypatch.setattr(command, "get_project_members_with_project_id", get_members)
    print_result = Mock()
    monkeypatch.setattr(command, "print_according_to_format", print_result)

    command.main()

    get_members.assert_called_once_with(["project1", "project2"], include_inactive=False, parallelism=2)
    print_result.assert_called_once_with([{"user_id": "user1"}])


def test_list_project_members_parallel_keeps_project_order():
    command = object.__new__(ListProjectMembers)
    command.service = Mock()
    command.service.api.get_project.side_effect = lambda project_id: ({"title": project_id}, None)
    command.service.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: [{"project_id": project_id, "user_id": project_id}]

    members = command.get_project_members_with_project_id(["project1", "project2"], parallelism=2)

    assert [member["project_id"] for member in members] == ["project1", "project2"]
    assert [member["project_title"] for member in members] == ["project1", "project2"]
