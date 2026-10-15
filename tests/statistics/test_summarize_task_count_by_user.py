import json
from argparse import Namespace
from unittest.mock import Mock

import pandas
import pytest
from annofabapi.models import Task

from annofabcli.statistics.summarize_task_count_by_user import SummarizeTaskCountByUser, TaskStatusForSummary, create_task_count_summary_df


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


def test_create_task_count_summary_df_excludes_unassigned_task() -> None:
    task_list: list[Task] = [
        {"task_id": "task1", "account_id": None, "status": "not_started", "phase": "annotation"},
        {"task_id": "task2", "account_id": "account1", "status": "working", "phase": "annotation"},
    ]

    actual = create_task_count_summary_df(task_list)

    assert actual["account_id"].to_list() == ["account1"]
    assert actual["working"].to_list() == [1]


@pytest.mark.parametrize("output_format", ["csv", "json", "pretty_json"])
def test_empty_legacy_task_list_outputs_selected_format(tmp_path, output_format):

    source = tmp_path / "tasks.json"
    source.write_text("[]")
    output = tmp_path / "task_count.csv"
    args = Namespace(project_id="project1", task_json_file=source, temp_dir=None, format=output_format, output=output, yes=True)

    SummarizeTaskCountByUser(Mock(), Mock(), args).main()

    if output_format == "csv":
        df = pandas.read_csv(output)
        assert len(df) == 0
        assert df.columns.to_list() == ["user_id", "username", "biography", *[status.value for status in TaskStatusForSummary]]
    else:
        assert json.loads(output.read_text()) == []
