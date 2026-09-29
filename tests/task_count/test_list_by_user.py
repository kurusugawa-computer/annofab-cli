import pandas

from annofabcli.task_count.list_by_user import TaskStatusForSummary, create_task_count_summary_df


def test_task_status_for_summary_from_task() -> None:
    task = {"status": "not_started", "phase": "inspection"}

    assert TaskStatusForSummary.from_task(task) == TaskStatusForSummary.INSPECTION_NOT_STARTED


def test_create_task_count_summary_df() -> None:
    task_list = [
        {"task_id": "task1", "account_id": "account1", "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation"},
        {"task_id": "task3", "account_id": "account2", "status": "complete", "phase": "acceptance"},
    ]

    actual = create_task_count_summary_df(task_list)

    expected = pandas.DataFrame(
        [
            {
                "account_id": "account1",
                "annotation_not_started": 1,
                "inspection_not_started": 0,
                "acceptance_not_started": 0,
                "working": 1,
                "break": 0,
                "on_hold": 0,
                "complete": 0,
            },
            {
                "account_id": "account2",
                "annotation_not_started": 0,
                "inspection_not_started": 0,
                "acceptance_not_started": 0,
                "working": 0,
                "break": 0,
                "on_hold": 0,
                "complete": 1,
            },
        ]
    )
    pandas.testing.assert_frame_equal(actual[expected.columns], expected, check_dtype=False, check_names=False)
