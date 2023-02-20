from annofabcli.statistics.list_worktime import WorktimeFromTaskHistoryEvent, get_df_worktime
from annofabcli.task_history_event.list_worktime import SimpleTaskHistoryEvent


class TestListWorktime:
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
                start_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-01T23:00:00.000+09:00", status="working"
                ),
                end_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-02T02:00:00.000+09:00", status="on_holding"
                ),
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
                start_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-03T22:00:00.000+09:00", status="working"
                ),
                end_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-03T23:00:00.000+09:00", status="on_holding"
                ),
            ),
        ]

        member_list = [
            {"account_id": "alice", "user_id": "alice", "username": "Alice", "biography": "U.S."},
            {"account_id": "bob", "user_id": "bob", "username": "Bob", "biography": "Japan"},
        ]
        df = get_df_worktime(event_list, member_list)
