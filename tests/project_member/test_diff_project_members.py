import json
from argparse import Namespace
from unittest.mock import Mock

import pytest
import yaml
from annofabapi.models import ProjectMember

from annofabcli.project_member.diff_project_members import DiffProjectMembers


def member(user_id: str, role: str = "worker", status: str = "active", inspection_rate: int | None = None) -> ProjectMember:
    return {
        "user_id": user_id,
        "account_id": user_id,
        "member_role": role,
        "sampling_inspection_rate": inspection_rate,
        "sampling_acceptance_rate": None,
        "member_status": status,
        "updated_datetime": "updated",
    }


@pytest.mark.parametrize("output_format", ["text", "detail_text", "json", "pretty_json"])
def test_diff_reports_left_to_right_changes_without_writing(tmp_path, output_format):
    service = Mock()
    service.api.login_user_id = "myself"
    left = [member("removed"), member("changed", inspection_rate=10), member("same"), member("myself"), member("outside")]
    right = [member("changed", "owner", inspection_rate=20), member("same"), member("myself", "owner"), member("added"), member("inactive", status="inactive")]
    service.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: left if project_id == "left" else right
    output = tmp_path / "diff"
    command = DiffProjectMembers(service, Mock(), Namespace(yes=False, left_project_id="left", right_project_id="right", format=output_format, output=str(output)))
    command.main()
    if output_format in ("json", "pretty_json"):
        record = json.loads(output.read_text())
        assert record["left_project_id"] == "left"
        assert record["right_project_id"] == "right"
        assert record["added_user_ids"] == ["added"]
        assert record["removed_user_ids"] == ["outside", "removed"]
        changed = {m["user_id"]: m for m in record["changed_members"]}
        assert set(changed) == {"changed", "myself"}
        assert changed["changed"]["changes"] == {
            "member_role": {"left": "worker", "right": "owner"},
            "sampling_inspection_rate": {"left": 10, "right": 20},
        }
    else:
        text = output.read_text()
        assert text.startswith("[project_members]\n")
        record = yaml.safe_load(text.removeprefix("[project_members]\n"))
        assert record["left_project_id"] == "left"
        assert record["right_project_id"] == "right"
        assert record["added"] == ["added"]
        assert record["removed"] == ["outside", "removed"]
        changed = {m["user_id"]: m for m in record["changed"]}
        assert set(changed) == {"changed", "myself"}
        if output_format == "text":
            assert changed["changed"]["fields"] == ["member_role", "sampling_inspection_rate"]
            assert "changes" not in changed["changed"]
        else:
            assert changed["changed"]["changes"] == {
                "member_role": {"left": "worker", "right": "owner"},
                "sampling_inspection_rate": {"left": 10, "right": 20},
            }
    service.wrapper.get_all_organization_members.assert_not_called()
    service.api.put_project_member.assert_not_called()


@pytest.mark.parametrize("output_format", ["text", "detail_text", "json", "pretty_json"])
@pytest.mark.parametrize("members", [[], [member("same")]])
def test_diff_empty_output(tmp_path, output_format, members):
    service = Mock()
    service.wrapper.get_all_project_members.return_value = members
    output = tmp_path / "diff"
    DiffProjectMembers(service, Mock(), Namespace(yes=False, left_project_id="left", right_project_id="right", format=output_format, output=str(output))).main()
    if output_format in ("json", "pretty_json"):
        assert json.loads(output.read_text()) == {"left_project_id": "left", "right_project_id": "right", "added_user_ids": [], "removed_user_ids": [], "changed_members": []}
    else:
        assert output.read_text() == ""


def test_diff_inactive_members_and_unset_rates(tmp_path):
    service = Mock()
    left = [member("rejoin", status="inactive"), member("leave"), member("changed", inspection_rate=10), member("inactive", status="inactive")]
    right = [member("rejoin"), member("leave", status="inactive"), member("changed"), member("inactive", "owner", status="inactive")]
    service.wrapper.get_all_project_members.side_effect = lambda project_id, **_kwargs: left if project_id == "left" else right
    output = tmp_path / "diff.json"
    DiffProjectMembers(service, Mock(), Namespace(yes=False, left_project_id="left", right_project_id="right", format="json", output=str(output))).main()
    record = json.loads(output.read_text())
    assert record == {
        "left_project_id": "left",
        "right_project_id": "right",
        "added_user_ids": ["rejoin"],
        "removed_user_ids": ["leave"],
        "changed_members": [{"user_id": "changed", "changes": {"sampling_inspection_rate": {"left": 10, "right": None}}}],
    }
    service.api.put_project_member.assert_not_called()


def test_diff_empty_text_does_not_write_stdout(capsys):
    service = Mock()
    service.wrapper.get_all_project_members.return_value = []
    DiffProjectMembers(service, Mock(), Namespace(yes=False, left_project_id="left", right_project_id="right", format="text", output=None)).main()
    assert capsys.readouterr().out == ""
