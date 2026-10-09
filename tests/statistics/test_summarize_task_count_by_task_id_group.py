import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas

from annofabcli.statistics.summarize_task_count_by_task_id_group import (
    SummarizeTaskCountByTaskId,
    TaskStatusForSummary,
    create_task_count_summary_df,
    get_task_id_prefix,
)

data_dir = Path("./tests/data/statistics")


def test_get_task_id_prefix():
    assert get_task_id_prefix("A_A_01", delimiter="_") == "A_A"
    assert get_task_id_prefix("abc", delimiter="_") == "unknown"


def test_create_task_count_summary_df():
    with (data_dir / "task.json").open(encoding="utf-8") as f:
        task_list = json.load(f)
    df = create_task_count_summary_df(task_list, task_id_delimiter="_", task_id_groups=None)
    assert len(df) == 1
    assert df.iloc[0]["task_id_group"] == "sample"


class TestTaskStatusForSummary:
    def test_from_task(self):
        task = {
            "phase": "annotation",
            "phase_stage": 1,
            "status": "not_started",
            "histories_by_phase": [
                {
                    "account_id": "alice",
                    "phase": "annotation",
                    "phase_stage": 1,
                    "worked": False,
                }
            ],
        }
        assert TaskStatusForSummary.from_task(task) == TaskStatusForSummary.ANNOTATION_NOT_STARTED


def test_empty_task_list_outputs_csv_header(tmp_path):

    source = tmp_path / "tasks.json"
    source.write_text("[]")
    output = tmp_path / "task_count.csv"
    args = Namespace(project_id="project1", task_json_file=source, task_id_delimiter="_", task_id_groups=None, temp_dir=None, format="csv", output=output, yes=True)

    SummarizeTaskCountByTaskId(Mock(), Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == ["task_id_group", *[status.value for status in TaskStatusForSummary], "sum"]
