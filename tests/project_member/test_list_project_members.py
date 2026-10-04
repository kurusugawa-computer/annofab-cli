from argparse import Namespace
from unittest.mock import Mock

from annofabcli.common.enums import OutputFormat
from annofabcli.project_member.list_users import ListProjectMembers


def test_list_project_members_csv_has_headers_when_empty(monkeypatch):
    command = object.__new__(ListProjectMembers)
    command.args = Namespace(project_id="project_id", include_inactive=False, format=OutputFormat.CSV.value)
    command.service = Mock()
    command.service.api.get_project.return_value = ({"title": "project"}, None)
    command.service.wrapper.get_all_project_members.return_value = []
    print_csv = Mock()
    monkeypatch.setattr(command, "print_csv", print_csv)

    command.main()

    actual_dataframe = print_csv.call_args.args[0]
    assert list(actual_dataframe.columns) == ListProjectMembers.PRIOR_COLUMNS
