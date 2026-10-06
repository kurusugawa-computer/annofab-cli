import json
from dataclasses import replace
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.__main__ import create_parser
from annofabcli.task_history_event import summarize_worktime_by_user_and_date
from annofabcli.task_history_event.list_worktime import RequestOfTaskHistoryEvent, SimpleTaskHistoryEvent
from annofabcli.task_history_event.summarize_worktime_by_user_and_date import WORKTIME_COLUMNS, WorktimeFromTaskHistoryEvent, get_df_worktime


def run_command(arguments: list[str]) -> None:
    args = create_parser().parse_args(arguments)
    args.subcommand_func(args)


class TestSummarizeWorktimeByUserAndDate:
    def test_get_df_worktime(self):
        event_list = [
            WorktimeFromTaskHistoryEvent(
                project_id="prj1",
                task_id="task1",
                phase="annotation",
                phase_stage=1,
                account_id="alice",
                user_id="alice",
                username="Alice",
                worktime_hour=3.0,
                start_event=SimpleTaskHistoryEvent(task_history_id="unknown", created_datetime="2019-01-01T23:00:00.000+09:00", status="working"),
                end_event=SimpleTaskHistoryEvent(task_history_id="unknown", created_datetime="2019-01-02T02:00:00.000+09:00", status="on_holding"),
                end_event_request=RequestOfTaskHistoryEvent(status="on_holding", force=False, account_id="alice", user_id="alice", username="Alice"),
            ),
            WorktimeFromTaskHistoryEvent(
                project_id="prj1",
                task_id="task2",
                phase="acceptance",
                phase_stage=1,
                account_id="bob",
                user_id="bob",
                username="Bob",
                worktime_hour=1.0,
                start_event=SimpleTaskHistoryEvent(task_history_id="unknown", created_datetime="2019-01-03T22:00:00.000+09:00", status="working"),
                end_event=SimpleTaskHistoryEvent(task_history_id="unknown", created_datetime="2019-01-03T23:00:00.000+09:00", status="on_holding"),
                end_event_request=RequestOfTaskHistoryEvent(status="on_holding", force=False, account_id="bob", user_id="bob", username="Bob"),
            ),
        ]

        member_list = [
            {"account_id": "alice", "user_id": "alice", "username": "Alice", "biography": "U.S."},
            {"account_id": "bob", "user_id": "bob", "username": "Bob", "biography": "Japan"},
        ]
        df_actual = get_df_worktime(event_list, member_list)
        df_expected = pandas.DataFrame(
            {
                "date": ["2019-01-01", "2019-01-02", "2019-01-03"],
                "user_id": ["alice", "alice", "bob"],
                "annotation_worktime_hour": [1.0, 2.0, 0],
                "acceptance_worktime_hour": [0, 0, 1.0],
            }
        )
        assert df_actual[["date", "user_id", "annotation_worktime_hour", "acceptance_worktime_hour"]].equals(df_expected[["date", "user_id", "annotation_worktime_hour", "acceptance_worktime_hour"]])


def test_empty_summary():
    actual = get_df_worktime([], [])
    assert actual.empty
    assert list(actual.columns) == WORKTIME_COLUMNS


def test_summarize_multiple_tasks_and_phases():
    event = WorktimeFromTaskHistoryEvent(
        project_id="prj1",
        task_id="task1",
        phase="annotation",
        phase_stage=1,
        account_id="alice",
        user_id="alice",
        username="Alice",
        worktime_hour=1.0,
        start_event=SimpleTaskHistoryEvent(task_history_id="start", created_datetime="2026-10-01T10:00:00+09:00", status="working"),
        end_event=SimpleTaskHistoryEvent(task_history_id="end", created_datetime="2026-10-01T11:00:00+09:00", status="complete"),
        end_event_request=RequestOfTaskHistoryEvent(status="complete", force=False, account_id="alice", user_id="alice", username="Alice"),
    )
    events = [event, replace(event, task_id="task2"), replace(event, task_id="task3", phase="inspection")]
    actual = get_df_worktime(events, [{"account_id": "alice", "user_id": "alice", "username": "Alice", "biography": "Japan"}])
    assert actual.to_dict(orient="records") == [
        {
            "date": "2026-10-01",
            "account_id": "alice",
            "user_id": "alice",
            "username": "Alice",
            "biography": "Japan",
            "worktime_hour": 3.0,
            "annotation_worktime_hour": 2.0,
            "inspection_worktime_hour": 1.0,
            "acceptance_worktime_hour": 0,
        }
    ]


@pytest.fixture
def local_worktime_input(tmp_path, monkeypatch):
    members = [{"account_id": "alice", "user_id": "alice", "username": "Alice", "biography": "Japan"}]
    service = Mock()
    service.api.get_project.return_value = ({"title": "Project"}, None)
    service.wrapper.get_all_project_members.return_value = members
    monkeypatch.setattr(summarize_worktime_by_user_and_date, "build_annofabapi_resource_and_login", lambda _args: service)
    events = []
    for status, hour in [("working", 10), ("complete", 11)]:
        events.append(
            {
                "project_id": "prj1",
                "task_id": "task1",
                "phase": "annotation",
                "phase_stage": 1,
                "account_id": "alice",
                "task_history_id": status,
                "status": status,
                "created_datetime": f"2026-10-01T{hour}:00:00+09:00",
                "request": {"status": status, "force": False, "account_id": "alice"},
            }
        )
    path = tmp_path / "events.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


@pytest.mark.parametrize("command", [["statistics", "list_worktime"], ["task_history_event", "summarize_worktime_by_user_and_date"]])
def test_command_csv_and_deprecation(command, local_worktime_input, tmp_path, caplog):
    output = tmp_path / "worktime.csv"
    run_command([*command, "--project_id", "prj1", "--task_history_event_json", str(local_worktime_input), "--output", str(output)])
    actual = pandas.read_csv(output)
    assert actual["worktime_hour"].tolist() == [1.0]
    assert actual["date"].tolist() == ["2026-10-01"]
    assert ("[DEPRECATED]" in caplog.text) == (command[0] == "statistics")
    if command[0] == "statistics":
        assert "task_history_event summarize_worktime_by_user_and_date" in caplog.text


@pytest.mark.parametrize("output_format", ["json", "pretty_json"])
def test_command_json(output_format, local_worktime_input, tmp_path):
    output = tmp_path / "worktime.json"
    run_command(
        [
            "task_history_event",
            "summarize_worktime_by_user_and_date",
            "--project_id",
            "prj1",
            "--task_history_event_json",
            str(local_worktime_input),
            "--format",
            output_format,
            "--output",
            str(output),
        ]
    )
    actual = json.loads(output.read_text(encoding="utf-8"))
    assert actual[0]["worktime_hour"] == 1.0
    assert actual[0]["user_id"] == "alice"


@pytest.mark.parametrize("output_format", ["csv", "json"])
@pytest.mark.parametrize("command", [["statistics", "list_worktime"], ["task_history_event", "summarize_worktime_by_user_and_date"]])
def test_command_empty(command, output_format, local_worktime_input, tmp_path):
    local_worktime_input.write_text("[]", encoding="utf-8")
    output = tmp_path / "empty"
    run_command(
        [
            *command,
            "--project_id",
            "prj1",
            "--task_history_event_json",
            str(local_worktime_input),
            "--format",
            output_format,
            "--output",
            str(output),
        ]
    )
    if output_format == "csv":
        actual = pandas.read_csv(output)
        assert actual.empty
        assert list(actual.columns) == WORKTIME_COLUMNS
    else:
        assert json.loads(output.read_text(encoding="utf-8")) == []
