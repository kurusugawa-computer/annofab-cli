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
            "account_id": None,
            "phase": "annotation",
            "input_data_count": 0,
            "video_duration_hour": 0,
            "video_duration_minute": 0,
            "task_status_for_summary": "never_worked.unassigned",
        }
    ]


def test_create_df_task_treats_not_started_task_with_worktime_as_worked() -> None:
    task_list = [create_task(task_id="task1", account_id="account1")]
    task_history_dict = {
        "task1": [
            {
                "phase": "annotation",
                "accumulated_labor_time_milliseconds": "PT1S",
            }
        ]
    }

    actual = create_df_task(task_list, task_history_dict)

    assert actual["task_status_for_summary"].to_list() == ["worked.not_rejected"]


def test_create_df_task_treats_rejected_not_started_task_as_worked() -> None:
    task = create_task(task_id="task1", account_id="account1")
    task["histories_by_phase"] = [
        {"phase": "inspection", "phase_stage": 1, "worked": True},
        {"phase": "annotation", "phase_stage": 1, "worked": False},
    ]

    actual = create_df_task([task], {"task1": []})

    assert actual["task_status_for_summary"].to_list() == ["worked.not_rejected"]
