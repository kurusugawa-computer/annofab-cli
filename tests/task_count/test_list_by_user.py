from argparse import Namespace
from unittest.mock import Mock

import pandas
from annofabapi.models import Task

from annofabcli.task_count.common import SUMMARY_COLUMNS
from annofabcli.task_count.list_by_phase import AggregationUnit
from annofabcli.task_count.list_by_user import (
    UNASSIGNED_ACCOUNT_ID,
    ListTaskCountByUser,
    TaskStatusForSummary,
    create_legacy_task_count_summary_df,
    create_task_count_summary_df,
    summarize_df_task_by_user,
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

    assert actual[["account_id", "annotation_not_started", "working", "complete"]].to_dict(orient="records") == [
        {"account_id": "account1", "annotation_not_started": 1, "working": 1, "complete": 0},
        {"account_id": "account2", "annotation_not_started": 0, "working": 0, "complete": 1},
    ]


def test_summarize_df_task_by_user_with_metadata_keys() -> None:
    df_task = pandas.DataFrame(
        [
            {"account_id": "account1", "phase": "annotation", "task_status_for_summary": "worked.not_rejected", "metadata.dataset": "train"},
            {"account_id": "account1", "phase": "acceptance", "task_status_for_summary": "complete", "metadata.dataset": "validation"},
            {"account_id": "account1", "phase": "annotation", "task_status_for_summary": "on_hold", "metadata.dataset": None},
        ]
    )

    actual = summarize_df_task_by_user(df_task, metadata_keys=["dataset"])

    assert len(actual) == 3
    assert actual["metadata.dataset"].isna().sum() == 1
    assert actual.set_index("metadata.dataset").loc["train", "annotation.worked"] == 1
    assert actual.set_index("metadata.dataset").loc["validation", "acceptance.complete"] == 1


def test_summarize_df_task_by_user_includes_unassigned_task() -> None:
    df_task = pandas.DataFrame(
        [
            {"account_id": None, "phase": "annotation", "task_status_for_summary": "never_worked.unassigned", "metadata.dataset": "train"},
            {"account_id": "account1", "phase": "annotation", "task_status_for_summary": "worked.not_rejected", "metadata.dataset": "train"},
        ]
    )

    actual = summarize_df_task_by_user(df_task, metadata_keys=["dataset"])

    assert set(actual["account_id"]) == {"account1", UNASSIGNED_ACCOUNT_ID}
    assert actual[SUMMARY_COLUMNS].sum(axis="columns").sum() == len(df_task)


def test_summarize_df_task_by_user_with_multiple_metadata_keys() -> None:
    df_task = pandas.DataFrame(
        [
            {
                "account_id": "account1",
                "phase": "annotation",
                "task_status_for_summary": "worked.not_rejected",
                "metadata.dataset": "train",
                "metadata.location": "tokyo",
            },
            {
                "account_id": "account1",
                "phase": "annotation",
                "task_status_for_summary": "worked.not_rejected",
                "metadata.dataset": "validation",
                "metadata.location": "osaka",
            },
        ]
    )

    actual = summarize_df_task_by_user(df_task, metadata_keys=["dataset", "location"])

    assert actual[["metadata.dataset", "metadata.location"]].to_dict(orient="records") == [
        {"metadata.dataset": "train", "metadata.location": "tokyo"},
        {"metadata.dataset": "validation", "metadata.location": "osaka"},
    ]


def test_summarize_df_task_by_user_with_input_data_count() -> None:
    df_task = pandas.DataFrame(
        [
            {
                "account_id": "account1",
                "phase": "annotation",
                "task_status_for_summary": "never_worked.assigned",
                "input_data_count": 2,
            },
            {
                "account_id": "account1",
                "phase": "annotation",
                "task_status_for_summary": "worked.not_rejected",
                "input_data_count": 3,
            },
        ]
    )

    actual = summarize_df_task_by_user(df_task, unit=AggregationUnit.INPUT_DATA)

    assert actual.loc[0, "annotation.never_worked"] == 2
    assert actual.loc[0, "annotation.worked"] == 3


def test_summarize_df_task_by_user_with_empty_task_list() -> None:
    actual = summarize_df_task_by_user(pandas.DataFrame())

    assert actual.columns.to_list() == ["account_id", *SUMMARY_COLUMNS]
    assert len(actual) == 0


def test_create_summary_df_includes_unassigned_user() -> None:
    class StubListTaskCountByUser(ListTaskCountByUser):
        def create_user_df(self, project_id: str, account_id_list: list[str], *, include_unknown_account: bool = True) -> pandas.DataFrame:
            assert project_id == "project1"
            assert account_id_list == ["account1"]
            assert include_unknown_account
            return pandas.DataFrame([{"account_id": "account1", "user_id": "user1", "username": "user1", "biography": ""}])

    command = object.__new__(StubListTaskCountByUser)
    df_task = pandas.DataFrame(
        [
            {"account_id": None, "phase": "annotation", "task_status_for_summary": "never_worked.unassigned"},
            {"account_id": "account1", "phase": "inspection", "task_status_for_summary": "worked.not_rejected"},
        ]
    )

    actual = command.create_summary_df("project1", df_task)

    assert actual["user_id"].to_list() == ["user1", "unassigned"]
    assert actual[SUMMARY_COLUMNS].sum(axis="columns").to_list() == [1, 1]


def test_create_legacy_task_count_summary_df_excludes_unassigned_task() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": None, "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation"},
    ]

    actual = create_legacy_task_count_summary_df(task_list)

    assert actual["account_id"].to_list() == ["account1"]
    assert actual["working"].to_list() == [1]


def test_empty_legacy_task_list_outputs_csv_header(tmp_path):

    source = tmp_path / "tasks.json"
    source.write_text("[]")
    output = tmp_path / "task_count.csv"
    args = Namespace(project_id="project1", unit=AggregationUnit.TASK.value, legacy_output=True, task_json=source, temp_dir=None, format="csv", output=output, yes=True)

    ListTaskCountByUser(Mock(), Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == ["user_id", "username", "biography", *[status.value for status in TaskStatusForSummary]]
