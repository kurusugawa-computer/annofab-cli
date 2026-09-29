import pandas

from annofabcli.task_count.common import SUMMARY_COLUMNS
from annofabcli.task_count.list_by_metadata import summarize_df_task_by_metadata
from annofabcli.task_count.list_by_phase import AggregationUnit


def test_summarize_df_task_by_metadata() -> None:
    df_task = pandas.DataFrame(
        [
            {
                "phase": "annotation",
                "task_status_for_summary": "never_worked.unassigned",
                "input_data_count": 1,
                "metadata.dataset": "train",
            },
            {
                "phase": "inspection",
                "task_status_for_summary": "worked.rejected",
                "input_data_count": 2,
                "metadata.dataset": "train",
            },
            {
                "phase": "annotation",
                "task_status_for_summary": "complete",
                "input_data_count": 3,
                "metadata.dataset": None,
            },
        ]
    )

    actual = summarize_df_task_by_metadata(df_task, metadata_keys=["dataset"])

    assert actual.columns.to_list() == ["metadata.dataset", *SUMMARY_COLUMNS]
    assert actual["metadata.dataset"].to_list()[:1] == ["train"]
    assert pandas.isna(actual["metadata.dataset"].iloc[1])
    assert actual[SUMMARY_COLUMNS].sum(axis="columns").to_list() == [2, 1]


def test_summarize_df_task_by_metadata_with_multiple_keys() -> None:
    df_task = pandas.DataFrame(
        [
            {
                "phase": "annotation",
                "task_status_for_summary": "worked.not_rejected",
                "input_data_count": 2,
                "metadata.dataset": "train",
                "metadata.location": "tokyo",
            },
            {
                "phase": "annotation",
                "task_status_for_summary": "on_hold",
                "input_data_count": 3,
                "metadata.dataset": "train",
                "metadata.location": None,
            },
        ]
    )

    actual = summarize_df_task_by_metadata(
        df_task,
        metadata_keys=["dataset", "location"],
        unit=AggregationUnit.INPUT_DATA,
    )

    assert len(actual) == 2
    assert actual[SUMMARY_COLUMNS].sum(axis="columns").sum() == 5


def test_summarize_df_task_by_metadata_with_empty_df() -> None:
    actual = summarize_df_task_by_metadata(pandas.DataFrame(), metadata_keys=["dataset"])

    assert actual.columns.to_list() == ["metadata.dataset", *SUMMARY_COLUMNS]
    assert len(actual) == 0
