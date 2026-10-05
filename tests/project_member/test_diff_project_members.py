import csv
import json
from argparse import Namespace
from unittest.mock import Mock

import pytest
from annofabapi.models import ProjectMember

from annofabcli.project_member.diff_project_members import DIFF_COLUMNS, DiffProjectMembers


def member(user_id: str, role: str = "worker", status: str = "active") -> ProjectMember:
    return {"user_id": user_id, "account_id": user_id, "member_role": role, "sampling_inspection_rate": None, "sampling_acceptance_rate": None, "member_status": status, "updated_datetime": "updated"}


@pytest.mark.parametrize("output_format", ["csv", "pretty_json"])
def test_diff_reports_changes_and_reasons_without_writing(tmp_path, output_format):
    service = Mock()
    service.api.login_user_id = "myself"
    source = [member("new"), member("changed"), member("same"), member("myself"), member("outside")]
    destination = [member("changed", "owner"), member("same"), member("myself", "owner"), member("extra"), member("inactive", status="inactive")]
    service.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: source if project_id == "src" else destination
    service.wrapper.get_all_organization_members.return_value = [{"account_id": m["account_id"]} for m in source if m["user_id"] != "outside"]
    output = tmp_path / "diff"
    command = DiffProjectMembers(service, Mock(), Namespace(yes=False, src_project_id="src", dest_project_id=["dest1", "dest2"], format=output_format, output=str(output)))
    command.main()
    if output_format == "csv":
        with output.open(encoding="utf-8-sig") as stream:
            records = list(csv.DictReader(stream))
    else:
        records = json.loads(output.read_text())
    assert len(records) == 10
    assert {r["dest_project_id"] for r in records} == {"dest1", "dest2"}
    by_user = {r["user_id"]: r for r in records}
    assert by_user["new"]["action"] == "add"
    assert by_user["changed"]["action"] == "update"
    assert by_user["changed"]["src_member_role"] == "worker"
    assert by_user["changed"]["dest_member_role"] == "owner"
    assert by_user["extra"]["action"] == "delete"
    assert by_user["myself"]["skip_reason"]
    assert by_user["outside"]["skip_reason"]
    service.api.put_project_member.assert_not_called()


@pytest.mark.parametrize("output_format", ["csv", "json"])
def test_diff_empty_output(tmp_path, output_format):
    service = Mock()
    service.wrapper.get_all_project_members.return_value = []
    service.wrapper.get_all_organization_members.return_value = []
    output = tmp_path / "diff"
    DiffProjectMembers(service, Mock(), Namespace(yes=False, src_project_id="src", dest_project_id=["dest"], format=output_format, output=str(output))).main()
    if output_format == "csv":
        assert output.read_text(encoding="utf-8-sig").strip() == ",".join(DIFF_COLUMNS)
    else:
        assert json.loads(output.read_text()) == []
