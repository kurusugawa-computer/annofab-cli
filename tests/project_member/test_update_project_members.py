from argparse import Namespace
from unittest.mock import Mock

import pytest
import requests

from annofabcli.project_member.update_project_members import UpdateProjectMembers, parse_project_member_updates, read_project_member_updates_from_csv


@pytest.fixture
def service():
    service = Mock()
    service.api.login_user_id = "myself"
    service.wrapper.get_all_project_members.return_value = [
        {
            "user_id": user_id,
            "member_status": status,
            "member_role": "accepter",
            "sampling_inspection_rate": 30,
            "sampling_acceptance_rate": 40,
            "updated_datetime": "2026-10-05T12:00:00+09:00",
        }
        for user_id, status in [("user1", "active"), ("user2", "active"), ("myself", "active"), ("inactive", "inactive")]
    ]
    return service


def test_update_members_preserves_omitted_values_and_clears_null_rates(service):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=True))
    updates = parse_project_member_updates([{"user_id": "user1", "member_role": "worker"}, {"user_id": "user2", "sampling_inspection_rate": None, "sampling_acceptance_rate": 0}])

    command.update_project_members("project", updates)

    calls = service.api.put_project_member.call_args_list
    assert [call.args for call in calls] == [("project", "user1"), ("project", "user2")]
    assert calls[0].kwargs["request_body"] == {
        "member_status": "active",
        "member_role": "worker",
        "sampling_inspection_rate": 30,
        "sampling_acceptance_rate": 40,
        "last_updated_datetime": "2026-10-05T12:00:00+09:00",
    }
    assert calls[1].kwargs["request_body"] == {
        "member_status": "active",
        "member_role": "accepter",
        "sampling_inspection_rate": None,
        "sampling_acceptance_rate": 0,
        "last_updated_datetime": "2026-10-05T12:00:00+09:00",
    }


@pytest.mark.parametrize(
    "changes, expected_rates",
    [
        ({"sampling_inspection_rate": 0}, (0, 40)),
        ({"sampling_acceptance_rate": 100}, (30, 100)),
        ({"sampling_inspection_rate": None, "sampling_acceptance_rate": None}, (None, None)),
        ({"member_role": "accepter", "sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}, (10, 20)),
    ],
)
def test_update_members_updates_own_rates_and_preserves_role(service, changes, expected_rates):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=True))

    command.update_project_members("project", parse_project_member_updates([{"user_id": "myself", **changes}]))

    service.api.put_project_member.assert_called_once()
    call = service.api.put_project_member.call_args
    assert call.args == ("project", "myself")
    assert call.kwargs["request_body"] == {
        "member_status": "active",
        "member_role": "accepter",
        "sampling_inspection_rate": expected_rates[0],
        "sampling_acceptance_rate": expected_rates[1],
        "last_updated_datetime": "2026-10-05T12:00:00+09:00",
    }


@pytest.mark.parametrize("rates", [{}, {"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}])
def test_update_members_skips_own_role_change_absent_inactive_and_empty_changes(service, rates):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=True))
    updates = parse_project_member_updates(
        [
            {"user_id": "myself", "member_role": "worker", **rates},
            {"user_id": "absent", "member_role": "worker"},
            {"user_id": "inactive", "member_role": "worker"},
            {"user_id": "user1"},
        ]
    )

    command.update_project_members("project", updates)

    service.api.put_project_member.assert_not_called()


def test_update_members_respects_confirmation(service, monkeypatch):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=False))
    monkeypatch.setattr("annofabcli.common.cli.prompt_yesnoall", lambda _message: (False, False))

    command.update_project_members("project", parse_project_member_updates([{"user_id": "user1", "member_role": "worker"}]))

    service.api.put_project_member.assert_not_called()


def test_update_members_continues_after_api_failure(service):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=True))
    service.api.put_project_member.side_effect = [requests.HTTPError(), ({}, None)]

    command.update_project_members("project", parse_project_member_updates([{"user_id": user_id, "member_role": "worker"} for user_id in ["user1", "user2"]]))

    assert [call.args[1] for call in service.api.put_project_member.call_args_list] == ["user1", "user2"]


def test_read_csv_preserves_blanks_and_string_user_ids(tmp_path):
    csv_path = tmp_path / "members.csv"
    csv_path.write_text("user_id,member_role,sampling_inspection_rate,sampling_acceptance_rate\n001,worker,,0\n002,,100,\n", encoding="utf-8")

    updates = read_project_member_updates_from_csv(csv_path)

    assert [member.model_dump(mode="json", exclude_unset=True) for member in updates] == [
        {"user_id": "001", "member_role": "worker", "sampling_acceptance_rate": 0},
        {"user_id": "002", "sampling_inspection_rate": 100},
    ]


@pytest.mark.parametrize(
    "value",
    [
        {"user_id": "user1", "member_role": "worker"},
        [{"member_role": "worker"}],
        [{"user_id": "", "member_role": "worker"}],
        [{"user_id": "user1", "member_role": None}],
        [{"user_id": "user1", "member_role": "invalid"}],
        [{"user_id": "user1", "sampling_inspection_rate": -1}],
        [{"user_id": "user1", "sampling_acceptance_rate": 101}],
        [{"user_id": "user1", "sampling_acceptance_rate": 1.5}],
        [{"user_id": "user1", "sampling_acceptance_rate": True}],
        [{"user_id": "user1", "sampling_acceptance_rate": "10"}],
        [{"user_id": "user1", "unknown": 10}],
        [{"user_id": "user1", "member_role": "worker"}, {"user_id": "user1", "member_role": "owner"}],
    ],
)
def test_parse_updates_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        parse_project_member_updates(value)


def test_invalid_json_does_not_update_any_members(service):
    command = UpdateProjectMembers(service, Mock(), Namespace(yes=True, csv=None, json='[{"user_id":"user1","member_role":"worker"},{"user_id":"user2","member_role":null}]', project_id="project"))

    with pytest.raises(SystemExit) as exc_info:
        command.main()

    assert exc_info.value.code == 2
    service.api.put_project_member.assert_not_called()


@pytest.mark.parametrize("input_format", ["csv", "json"])
def test_main_reads_updates_from_file(service, tmp_path, input_format):
    input_path = tmp_path / f"members.{input_format}"
    if input_format == "csv":
        input_path.write_text("user_id,member_role\nuser1,worker\n", encoding="utf-8")
    else:
        input_path.write_text('[{"user_id":"user1","member_role":"worker"}]', encoding="utf-8")
    command = UpdateProjectMembers(
        service,
        Mock(),
        Namespace(
            yes=True,
            project_id="project",
            csv=input_path if input_format == "csv" else None,
            json=f"file://{input_path}" if input_format == "json" else None,
        ),
    )

    command.main()

    service.api.put_project_member.assert_called_once()
    assert service.api.put_project_member.call_args.kwargs["request_body"]["member_role"] == "worker"
