import pandas
from annofabapi.models import Task

from annofabcli.task_count.list_by_task_id_group import SUMMARY_COLUMNS
from annofabcli.task_count.list_by_user import (
    UNASSIGNED_ACCOUNT_ID,
    ListTaskCountByUser,
    TaskStatusForSummary,
    create_legacy_task_count_summary_df,
    create_task_count_summary_df,
)


def test_task_status_for_summary_from_task() -> None:
    task = {"status": "not_started", "phase": "inspection"}

    assert TaskStatusForSummary.from_task(task) == TaskStatusForSummary.INSPECTION_NOT_STARTED


def test_create_task_count_summary_df() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": "account1", "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation"},
        {"task_id": "task3", "account_id": "account2", "status": "complete", "phase": "acceptance"},
    ]

    actual = create_task_count_summary_df(task_list)

    expected = pandas.DataFrame(
        [
            {
                "account_id": "account1",
                "annotation.never_worked": 1,
                "annotation.worked": 1,
                "annotation.on_hold": 0,
                "inspection.never_worked": 0,
                "inspection.worked": 0,
                "inspection.on_hold": 0,
                "acceptance.never_worked": 0,
                "acceptance.worked": 0,
                "acceptance.on_hold": 0,
                "acceptance.complete": 0,
                "total": 2,
            },
            {
                "account_id": "account2",
                "annotation.never_worked": 0,
                "annotation.worked": 0,
                "annotation.on_hold": 0,
                "inspection.never_worked": 0,
                "inspection.worked": 0,
                "inspection.on_hold": 0,
                "acceptance.never_worked": 0,
                "acceptance.worked": 0,
                "acceptance.on_hold": 0,
                "acceptance.complete": 1,
                "total": 1,
            },
        ]
    )
    pandas.testing.assert_frame_equal(actual[expected.columns], expected, check_dtype=False, check_names=False)


def test_create_task_count_summary_df_with_metadata_keys() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": "account1", "status": "working", "phase": "annotation", "metadata": {"dataset": "train"}},
        {"task_id": "task2", "account_id": "account1", "status": "complete", "phase": "acceptance", "metadata": {"dataset": "validation"}},
        {"task_id": "task3", "account_id": "account1", "status": "on_hold", "phase": "annotation", "metadata": {}},
    ]

    actual = create_task_count_summary_df(task_list, metadata_keys=["dataset"])

    assert len(actual) == 3
    assert actual["metadata.dataset"].isna().sum() == 1
    assert actual.set_index("metadata.dataset").loc["train", "annotation.worked"] == 1
    assert actual.set_index("metadata.dataset").loc["validation", "acceptance.complete"] == 1


def test_create_task_count_summary_df_includes_unassigned_task() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": None, "status": "not_started", "phase": "annotation", "metadata": {"dataset": "train"}},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation", "metadata": {"dataset": "train"}},
    ]

    actual = create_task_count_summary_df(task_list, metadata_keys=["dataset"])

    assert set(actual["account_id"]) == {"account1", UNASSIGNED_ACCOUNT_ID}
    assert actual["total"].sum() == len(task_list)


def test_create_task_count_summary_df_with_multiple_metadata_keys() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": "account1", "status": "working", "phase": "annotation", "metadata": {"dataset": "train", "location": "tokyo"}},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation", "metadata": {"dataset": "validation", "location": "osaka"}},
    ]

    actual = create_task_count_summary_df(task_list, metadata_keys=["dataset", "location"])

    assert actual[["metadata.dataset", "metadata.location"]].to_dict(orient="records") == [
        {"metadata.dataset": "train", "metadata.location": "tokyo"},
        {"metadata.dataset": "validation", "metadata.location": "osaka"},
    ]


def test_create_task_count_summary_df_with_empty_task_list() -> None:
    actual = create_task_count_summary_df([])

    assert actual.columns.to_list() == ["account_id", *SUMMARY_COLUMNS, "total"]
    assert len(actual) == 0


def test_create_summary_df_includes_unassigned_user() -> None:
    class StubListTaskCountByUser(ListTaskCountByUser):
        def create_user_df(self, project_id: str, account_id_list: list[str], *, include_unknown_account: bool = True) -> pandas.DataFrame:
            assert project_id == "project1"
            assert account_id_list == ["account1"]
            assert include_unknown_account
            return pandas.DataFrame([{"account_id": "account1", "user_id": "user1", "username": "user1", "biography": ""}])

    command = object.__new__(StubListTaskCountByUser)
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": None, "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "inspection"},
    ]

    actual = command.create_summary_df("project1", task_list)

    assert actual[["user_id", "total"]].to_dict(orient="records") == [
        {"user_id": "user1", "total": 1},
        {"user_id": "unassigned", "total": 1},
    ]


def test_create_legacy_task_count_summary_df_excludes_unassigned_task() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": None, "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation"},
    ]

    actual = create_legacy_task_count_summary_df(task_list)

    assert actual["account_id"].to_list() == ["account1"]
    assert actual["working"].to_list() == [1]
