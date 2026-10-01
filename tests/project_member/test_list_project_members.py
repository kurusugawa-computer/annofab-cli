from argparse import Namespace
from unittest.mock import Mock

from annofabcli.common.enums import OutputFormat
from annofabcli.project_member.list_users import ListProjectMembers


def test_list_project_members_csv_has_headers_when_empty(monkeypatch):
    command = object.__new__(ListProjectMembers)
    command.args = Namespace(project_id=["project_id"], include_inactive=False, format=OutputFormat.CSV.value)
    monkeypatch.setattr(command, "get_project_members_with_project_id", Mock(return_value=[]))
    print_csv = Mock()
    monkeypatch.setattr(command, "print_csv", print_csv)

    command.main()

    actual_dataframe = print_csv.call_args.args[0]
    assert list(actual_dataframe.columns) == ListProjectMembers.PRIOR_COLUMNS
