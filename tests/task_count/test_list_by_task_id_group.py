import pandas
import pytest

from annofabcli.task_count.list_by_phase import AggregationUnit
from annofabcli.task_count.list_by_task_id_group import SUMMARY_COLUMNS, get_task_id_prefix, summarize_df_task_by_task_id_group


def test_get_task_id_prefix() -> None:
    assert get_task_id_prefix("A_A_01", delimiter="_") == "A_A"
    assert get_task_id_prefix("abc", delimiter="_") == "unknown"


def test_get_task_id_prefix_with_component_count() -> None:
    task_id = "20260902_second_f00075528-00075822_cam5"

    assert get_task_id_prefix(task_id, delimiter="_") == "20260902_second_f00075528-00075822"
    assert get_task_id_prefix(task_id, delimiter="_", component_count=2) == "20260902_second"
    assert get_task_id_prefix(task_id, delimiter="_", component_count=5) == "unknown"


def create_df_task() -> pandas.DataFrame:
    statuses = [
        ("annotation", "never_worked.unassigned"),
        ("annotation", "never_worked.assigned"),
        ("annotation", "worked.not_rejected"),
        ("annotation", "worked.rejected"),
        ("annotation", "on_hold"),
        ("inspection", "never_worked.assigned"),
        ("inspection", "worked.not_rejected"),
        ("inspection", "on_hold"),
        ("acceptance", "never_worked.unassigned"),
        ("acceptance", "worked.rejected"),
        ("acceptance", "on_hold"),
        ("annotation", "complete"),
    ]
    return pandas.DataFrame(
        [
            {
                "task_id": f"sample_{index:02}",
                "phase": phase,
                "task_status_for_summary": status,
                "input_data_count": index,
                "video_duration_hour": index / 10,
                "video_duration_minute": index * 6,
            }
            for index, (phase, status) in enumerate(statuses, start=1)
        ]
    )


def test_summarize_df_task_by_task_id_group_with_task_count() -> None:
    actual = summarize_df_task_by_task_id_group(
        create_df_task(),
        task_id_delimiter="_",
        task_id_groups=None,
    )

    assert actual.to_dict(orient="records") == [
        {
            "task_id_group": "sample",
            "annotation.never_worked": 2,
            "annotation.worked": 2,
            "annotation.on_hold": 1,
            "inspection.never_worked": 1,
            "inspection.worked": 1,
            "inspection.on_hold": 1,
            "acceptance.never_worked": 1,
            "acceptance.worked": 1,
            "acceptance.on_hold": 1,
            "acceptance.complete": 1,
            "total": 12,
        }
    ]


def test_summarize_df_task_by_task_id_group_with_component_count() -> None:
    df_task = create_df_task().iloc[:1].assign(task_id="20260902_second_f00075528-00075822_cam5")

    actual = summarize_df_task_by_task_id_group(
        df_task,
        task_id_delimiter="_",
        task_id_groups=None,
        task_id_group_component_count=2,
    )

    assert actual.iloc[0]["task_id_group"] == "20260902_second"


def test_summarize_df_task_by_task_id_group_with_input_data_count() -> None:
    actual = summarize_df_task_by_task_id_group(
        create_df_task(),
        task_id_delimiter="_",
        task_id_groups=None,
        unit=AggregationUnit.INPUT_DATA,
    )

    assert actual.to_dict(orient="records") == [
        {
            "task_id_group": "sample",
            "annotation.never_worked": 3,
            "annotation.worked": 7,
            "annotation.on_hold": 5,
            "inspection.never_worked": 6,
            "inspection.worked": 7,
            "inspection.on_hold": 8,
            "acceptance.never_worked": 9,
            "acceptance.worked": 10,
            "acceptance.on_hold": 11,
            "acceptance.complete": 12,
            "total": 78,
        }
    ]


@pytest.mark.parametrize(
    ("unit", "expected_total"),
    [
        (AggregationUnit.VIDEO_DURATION_HOUR, 7.8),
        (AggregationUnit.VIDEO_DURATION_MINUTE, 468),
    ],
)
def test_summarize_df_task_by_task_id_group_with_video_duration(unit: AggregationUnit, expected_total: float) -> None:
    actual = summarize_df_task_by_task_id_group(
        create_df_task(),
        task_id_delimiter="_",
        task_id_groups=None,
        unit=unit,
    )

    assert actual.iloc[0]["total"] == pytest.approx(expected_total)


def test_summarize_df_task_by_task_id_group_with_task_id_groups() -> None:
    actual = summarize_df_task_by_task_id_group(
        create_df_task().iloc[:2],
        task_id_delimiter=None,
        task_id_groups={"group1": ["sample_01"]},
    )

    assert actual["task_id_group"].to_list() == ["group1", "unknown"]
    assert actual["total"].to_list() == [1, 1]


def test_summarize_df_task_by_task_id_group_with_empty_df() -> None:
    actual = summarize_df_task_by_task_id_group(
        pandas.DataFrame(),
        task_id_delimiter="_",
        task_id_groups=None,
    )

    assert actual.columns.to_list() == ["task_id_group", *SUMMARY_COLUMNS, "total"]
    assert len(actual) == 0
