import json
from pathlib import Path

from annofabcli.statistics.summarize_task_count_by_task_id_group import (
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
