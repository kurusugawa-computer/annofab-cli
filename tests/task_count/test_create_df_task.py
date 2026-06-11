from annofabcli.task_count.list_by_phase import create_df_task


def create_task(*, task_id: str, status: str = "not_started", account_id: str | None = None) -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "phase": "annotation",
        "phase_stage": 1,
        "histories_by_phase": [],
        "account_id": account_id,
        "input_data_id_list": [],
        "metadata": {},
    }


def test_create_df_task_treats_missing_task_history_as_empty() -> None:
    task_list = [create_task(task_id="task1")]
    task_history_dict: dict[str, list[dict]] = {}

    actual = create_df_task(task_list, task_history_dict)

    assert actual.to_dict(orient="records") == [
        {
            "task_id": "task1",
            "phase": "annotation",
            "input_data_count": 0,
            "video_duration_hour": 0,
            "video_duration_minute": 0,
            "task_status_for_summary": "never_worked.unassigned",
        }
    ]
