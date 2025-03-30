from dataclasses import dataclass
from typing import Any

from annofabcli.task.list_tasks_added_task_history import (
    get_completed_datetime,
    get_first_acceptance_completed_datetime,
    get_first_acceptance_reached_datetime,
    get_post_rejection_acceptance_worktime_hour,
    get_post_rejection_annotation_worktime_hour,
    get_post_rejection_inspection_worktime_hour,
    is_acceptance_phase_skipped,
    is_inspection_phase_skipped,
)


@dataclass
class TaskInfo:
    task: dict[str, Any]
    task_histories: list[dict[str, Any]]


# タスク作成直後の状態
task_created_immediately = TaskInfo(
    task={
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_02",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
        "input_data_id_list": ["bbc5faf4-f22f-48ac-9393-b524cb3e0034"],
        "account_id": None,
        "histories_by_phase": [],
        "work_time_span": 0,
        "number_of_rejections": 0,
        "started_datetime": None,
        "updated_datetime": "2025-03-27T11:31:23.513+09:00",
        "operation_updated_datetime": "2025-03-27T11:31:23.513+09:00",
        "sampling": None,
        "metadata": {},
    },
    task_histories=[
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_02",
            "task_history_id": "f8e21d05-4726-4706-865c-52a85fd8f2ae",
            "started_datetime": None,
            "ended_datetime": None,
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "annotation",
            "phase_stage": 1,
            "account_id": None,
        }
    ],
)


complete_task = TaskInfo(
    task={
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_07",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_id_list": ["8dcb2786-d818-463f-ac73-b728cd65837c"],
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
        "histories_by_phase": [
            {"account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299", "phase": "annotation", "phase_stage": 1, "worked": True},
            {"account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299", "phase": "acceptance", "phase_stage": 1, "worked": True},
        ],
        "work_time_span": 6099,
        "number_of_rejections": 0,
        "started_datetime": "2025-03-30T13:53:23.546+09:00",
        "updated_datetime": "2025-03-30T13:53:27.067+09:00",
        "operation_updated_datetime": "2025-03-30T13:53:27.067+09:00",
        "sampling": None,
        "metadata": {},
    },
    task_histories=[
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_07",
            "task_history_id": "74b8fe69-e397-4b13-8a50-f34a72c3074b",
            "started_datetime": "2025-03-27T11:31:22.91+09:00",
            "ended_datetime": None,
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "annotation",
            "phase_stage": 1,
            "account_id": None,
        },
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_07",
            "task_history_id": "49d47a78-1fe9-4c67-b852-c75306c35a34",
            "started_datetime": "2025-03-27T11:35:53.332+09:00",
            "ended_datetime": "2025-03-27T11:35:55.935+09:00",
            "accumulated_labor_time_milliseconds": "PT2.603S",
            "phase": "annotation",
            "phase_stage": 1,
            "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
        },
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_07",
            "task_history_id": "45e862f9-a5be-4e20-ae4d-69178e6f1be3",
            "started_datetime": "2025-03-27T11:35:55.937+09:00",
            "ended_datetime": "2025-03-27T11:35:55.937+09:00",
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "inspection",
            "phase_stage": 1,
            "account_id": None,
        },
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_07",
            "task_history_id": "a30f77be-1d68-418b-bf71-b4cbaafc2c27",
            "started_datetime": "2025-03-27T11:35:55.939+09:00",
            "ended_datetime": "2025-03-27T11:35:55.939+09:00",
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "acceptance",
            "phase_stage": 1,
            "account_id": None,
        },
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250327_07",
            "task_history_id": "520845d7-d362-400b-afbb-571b484535e0",
            "started_datetime": "2025-03-30T13:53:23.546+09:00",
            "ended_datetime": "2025-03-30T13:53:27.042+09:00",
            "accumulated_labor_time_milliseconds": "PT3.496S",
            "phase": "acceptance",
            "phase_stage": 1,
            "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
        },
    ],
)

# 差し戻し直後のタスク履歴。一度も完了状態になっていない
rejected_task_histories: list[dict[str, Any]] = [
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "d774ee09-5fc1-4707-9431-6ee6dbbacbf1",
        "started_datetime": "2025-03-27T11:31:22.91+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "7d3b0acb-c7f7-4ead-bdfd-359b0bcb0ea9",
        "started_datetime": "2025-03-29T05:47:25.056+09:00",
        "ended_datetime": "2025-03-30T14:04:32.805+09:00",
        "accumulated_labor_time_milliseconds": "PT37.926S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "fbfaae37-7db3-4e4b-97e5-faaa4669ca78",
        "started_datetime": "2025-03-30T14:04:32.806+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "0e5c0a23-2557-4aa7-bce2-bae2cddc30f4",
        "started_datetime": "2025-03-30T14:07:32.043+09:00",
        "ended_datetime": "2025-03-30T14:07:37.651+09:00",
        "accumulated_labor_time_milliseconds": "PT5.608S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "9d31004f-8737-4f13-9239-bf5b45c8ee30",
        "started_datetime": "2025-03-30T14:07:37.652+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "296f4a3a-196a-48e0-bb71-2d50eb465088",
        "started_datetime": "2025-03-30T14:07:54.361+09:00",
        "ended_datetime": "2025-03-30T14:08:13.167+09:00",
        "accumulated_labor_time_milliseconds": "PT18.806S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_23",
        "task_history_id": "a4628da0-c363-425f-9476-08e58b0ea794",
        "started_datetime": None,
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
]


rejected_inspection_acceptance_phase_task_histories: list[dict[str, Any]] = [
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
    actual_seconds = get_post_rejection_annotation_worktime_hour(rejected_inspection_acceptance_phase_task_histories) * 3600
    assert int(actual_seconds) == 23


def test__get_post_rejection_inspection_worktime_hour():
    assert get_post_rejection_inspection_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_inspection_worktime_hour(rejected_inspection_acceptance_phase_task_histories) * 3600
    assert int(actual_seconds) == 39


def test__get_post_rejection_acceptance_worktime_hour():
    assert get_post_rejection_acceptance_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_acceptance_worktime_hour(rejected_inspection_acceptance_phase_task_histories) * 3600
    assert int(actual_seconds) == 7


not_skipped_task_histories: list[dict[str, Any]] = [
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "094596e2-c931-40bf-acb6-c6a5925a4278",
        "started_datetime": "2025-03-27T11:31:22.91+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "9fc4209d-f1c1-40a4-b6cf-1160493ca05e",
        "started_datetime": "2025-03-27T11:38:28.395+09:00",
        "ended_datetime": "2025-03-27T11:38:31.33+09:00",
        "accumulated_labor_time_milliseconds": "PT2.935S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "18cd0166-6656-4944-b7c4-eb997ca8e968",
        "started_datetime": "2025-03-27T11:38:31.331+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "3c5791da-f96a-4e6a-a9a2-0ad8e8fc369f",
        "started_datetime": "2025-03-27T11:38:42.198+09:00",
        "ended_datetime": "2025-03-27T11:38:44.59+09:00",
        "accumulated_labor_time_milliseconds": "PT2.392S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "d8bc31ab-76bb-4b2f-9028-d2c2254016b0",
        "started_datetime": "2025-03-27T11:38:44.591+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_30",
        "task_history_id": "5e8e8d99-da4e-418b-9d9c-a9ab3e0dfb88",
        "started_datetime": "2025-03-27T11:38:56.67+09:00",
        "ended_datetime": "2025-03-27T11:38:59.05+09:00",
        "accumulated_labor_time_milliseconds": "PT2.38S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
]

skipped_task_histories: list[dict[str, Any]] = [
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_07",
        "task_history_id": "74b8fe69-e397-4b13-8a50-f34a72c3074b",
        "started_datetime": "2025-03-27T11:31:22.91+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_07",
        "task_history_id": "49d47a78-1fe9-4c67-b852-c75306c35a34",
        "started_datetime": "2025-03-27T11:35:53.332+09:00",
        "ended_datetime": "2025-03-27T11:35:55.935+09:00",
        "accumulated_labor_time_milliseconds": "PT2.603S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_07",
        "task_history_id": "45e862f9-a5be-4e20-ae4d-69178e6f1be3",
        "started_datetime": "2025-03-27T11:35:55.937+09:00",
        "ended_datetime": "2025-03-27T11:35:55.937+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250327_07",
        "task_history_id": "a30f77be-1d68-418b-bf71-b4cbaafc2c27",
        "started_datetime": "2025-03-27T11:35:55.939+09:00",
        "ended_datetime": "2025-03-27T11:35:55.939+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
]


def test__is_acceptance_phase_skipped():
    assert is_acceptance_phase_skipped(skipped_task_histories)
    assert not is_acceptance_phase_skipped(not_skipped_task_histories)


def test__is_inspection_phase_skipped():
    assert is_inspection_phase_skipped(skipped_task_histories)
    assert not is_inspection_phase_skipped(not_skipped_task_histories)


def test__get_first_acceptance_completed_datetime():
    assert get_first_acceptance_completed_datetime(complete_task.task_histories) == "2025-03-27T11:35:55.939+09:00"

    # 受入フェーズには到達したが差し戻されて、一度の完了状態に到達していない場合
    assert get_first_acceptance_completed_datetime(rejected_task_histories) is None


def test__get_first_acceptance_reached_datetime():
    assert get_first_acceptance_reached_datetime(rejected_task_histories) == "2025-03-30T14:07:37.651+09:00"

    # タスク作成直後の状態
    assert get_first_acceptance_reached_datetime(task_created_immediately.task_histories) is None


def test__get_completed_datetime():
    # 最後の履歴の終了日時が受入完了日時になる
    assert get_completed_datetime(complete_task.task, complete_task.task_histories) == "2025-03-30T13:53:27.042+09:00"
    assert get_completed_datetime(task_created_immediately.task, task_created_immediately.task_histories) is None
