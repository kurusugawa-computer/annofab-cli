"""タスク数の横持ち集計で共通して使用する処理。"""

from typing import assert_never

import pandas

from annofabcli.task_count.list_by_phase import AggregationUnit, TaskStatusForSummary

SUMMARY_COLUMNS = [
    "annotation.never_worked",
    "annotation.worked",
    "annotation.on_hold",
    "inspection.never_worked",
    "inspection.worked",
    "inspection.on_hold",
    "acceptance.never_worked",
    "acceptance.worked",
    "acceptance.on_hold",
    "acceptance.complete",
]
"""フェーズと状態別の集計結果に含める列。"""


def get_summary_status(task_status_for_summary: str) -> str:
    """詳細なタスク状態を横持ち集計用の状態に変換する。

    Args:
        task_status_for_summary: ``task_count list_by_phase`` で使用するタスク状態。

    Returns:
        ``never_worked``、``worked``、``on_hold``、``complete`` のいずれか。
    """
    if task_status_for_summary in {
        TaskStatusForSummary.NEVER_WORKED_UNASSIGNED.value,
        TaskStatusForSummary.NEVER_WORKED_ASSIGNED.value,
    }:
        return "never_worked"
    if task_status_for_summary in {
        TaskStatusForSummary.WORKED_NOT_REJECTED.value,
        TaskStatusForSummary.WORKED_REJECTED.value,
    }:
        return "worked"
    return task_status_for_summary


def summarize_df_task(
    df_task: pandas.DataFrame,
    *,
    group_columns: list[str],
    unit: AggregationUnit = AggregationUnit.TASK,
) -> pandas.DataFrame:
    """指定された列ごとに、フェーズと状態別の値を横持ちで集計する。

    Args:
        df_task: タスク情報を格納したDataFrame。
        group_columns: 集計のグループを表す列。
        unit: 集計の単位。

    Returns:
        グループごとの集計結果を格納したDataFrame。
    """
    result_columns = [*group_columns, *SUMMARY_COLUMNS]
    if len(df_task) == 0:
        return pandas.DataFrame(columns=result_columns)

    summary_status = df_task["task_status_for_summary"].map(get_summary_status)
    summary_phase = df_task["phase"].mask(summary_status == TaskStatusForSummary.COMPLETE.value, "acceptance")
    df = df_task.assign(summary_column=summary_phase + "." + summary_status)

    match unit:
        case AggregationUnit.TASK:
            df = df.assign(_aggregate_value=1)
        case AggregationUnit.INPUT_DATA:
            df = df.assign(_aggregate_value=df["input_data_count"])
        case AggregationUnit.VIDEO_DURATION_HOUR:
            df = df.assign(_aggregate_value=df["video_duration_hour"])
        case AggregationUnit.VIDEO_DURATION_MINUTE:
            df = df.assign(_aggregate_value=df["video_duration_minute"])
        case _ as unreachable:
            assert_never(unreachable)

    df = df.assign(_group_index=df.groupby(group_columns, dropna=False, sort=False).ngroup())
    df_group = df[["_group_index", *group_columns]].drop_duplicates(subset="_group_index")
    df_aggregate = df.pivot_table(
        values="_aggregate_value",
        index="_group_index",
        columns="summary_column",
        aggfunc="sum",
        fill_value=0,
    )
    df_summary = df_group.merge(df_aggregate, on="_group_index").drop(columns="_group_index")
    for column in SUMMARY_COLUMNS:
        if column not in df_summary.columns:
            df_summary[column] = 0

    return df_summary[result_columns].sort_values(group_columns, na_position="last").reset_index(drop=True)
