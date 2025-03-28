from typing import Any

from annofabcli.task.list_tasks_added_task_history import (
    get_post_rejection_acceptance_worktime_hour,
    get_post_rejection_annotation_worktime_hour,
    get_post_rejection_inspection_worktime_hour,
)

task_histories: list[dict[str, Any]] = [
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "555b5ccc-6c80-4c8f-b22f-8c5fd7ef274f",
        "started_datetime": "2025-03-23T16:14:33.796+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "bb0e04bc-4fe8-4eb2-8f5f-556d54b704cb",
        "started_datetime": "2025-03-23T16:14:49.992+09:00",
        "ended_datetime": "2025-03-23T16:14:53.657+09:00",
        "accumulated_labor_time_milliseconds": "PT3.665S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "18edf828-c702-41a7-aa0d-367ce1a0f0e0",
        "started_datetime": "2025-03-23T16:14:53.659+09:00",
        "ended_datetime": "2025-03-23T16:14:53.659+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "c15053ed-9813-4a16-a77a-a852daee7782",
        "started_datetime": "2025-03-23T16:14:53.661+09:00",
        "ended_datetime": "2025-03-23T16:14:53.661+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "e471f859-7cc9-4828-a6d4-a9b163f5ef67",
        "started_datetime": "2025-03-23T16:15:55.674+09:00",
        "ended_datetime": "2025-03-23T16:16:11.884+09:00",
        "accumulated_labor_time_milliseconds": "PT16.21S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "3345b4a9-610c-47a0-910a-3285ffa96e22",
        "started_datetime": "2025-03-23T16:16:17.631+09:00",
        "ended_datetime": "2025-03-23T16:16:27.045+09:00",
        "accumulated_labor_time_milliseconds": "PT9.414S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "62f6ce58-1684-4b8b-8ea4-c3cd00cf980f",
        "started_datetime": "2025-03-23T16:16:31.062+09:00",
        "ended_datetime": "2025-03-23T16:16:31.062+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "d73c5943-949e-4dbd-a01e-a7d8e7f7418d",
        "started_datetime": "2025-03-23T16:16:52.135+09:00",
        "ended_datetime": "2025-03-23T16:16:55.953+09:00",
        "accumulated_labor_time_milliseconds": "PT3.818S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "3bee8257-ca11-4f48-8a9c-6379e2a7a1d6",
        "started_datetime": "2025-03-23T16:16:55.954+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "122c6daa-b834-4c54-ba3f-86fe21b5f936",
        "started_datetime": "2025-03-23T16:17:06.434+09:00",
        "ended_datetime": "2025-03-23T16:17:13.042+09:00",
        "accumulated_labor_time_milliseconds": "PT6.608S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "e88ff387-7b17-430d-acb4-360deb956c2c",
        "started_datetime": "2025-03-23T16:17:13.043+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "f084a3a5-1cdb-4839-9317-0e85fbea87ae",
        "started_datetime": "2025-03-23T16:17:17.884+09:00",
        "ended_datetime": "2025-03-23T16:17:17.884+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "382dbb13-f13c-4758-9337-b1335e0d923f",
        "started_datetime": "2025-03-23T16:17:22.852+09:00",
        "ended_datetime": "2025-03-23T16:17:38.245+09:00",
        "accumulated_labor_time_milliseconds": "PT15.393S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "793c4098-26a3-46dd-842c-c94faa6350f0",
        "started_datetime": "2025-03-23T16:18:03.989+09:00",
        "ended_datetime": "2025-03-23T16:18:14.638+09:00",
        "accumulated_labor_time_milliseconds": "PT10.649S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "514e30a5-9bc5-4d0c-941b-976d4da468dd",
        "started_datetime": "2025-03-23T16:18:19.245+09:00",
        "ended_datetime": "2025-03-23T16:18:36.659+09:00",
        "accumulated_labor_time_milliseconds": "PT17.414S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "064f6af7-834e-4239-85ce-460fa86bc584",
        "started_datetime": "2025-03-23T16:18:39.818+09:00",
        "ended_datetime": "2025-03-23T16:18:47.494+09:00",
        "accumulated_labor_time_milliseconds": "PT7.676S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
]


def test__get_post_rejection_annotation_worktime_hour():
    assert get_post_rejection_annotation_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_annotation_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 23


def test__get_post_rejection_inspection_worktime_hour():
    assert get_post_rejection_inspection_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_inspection_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 39


def test__get_post_rejection_acceptance_worktime_hour():
    assert get_post_rejection_acceptance_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_acceptance_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 7
