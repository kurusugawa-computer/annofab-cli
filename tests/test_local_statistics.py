import json
from pathlib import Path

import pandas

from annofabcli.statistics.summarize_task_count_by_task_id_group import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table

out_path = Path("./tests/out/statistics")
data_path = Path("./tests/data/statistics")
out_path.mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"


class TestTable:
    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_path / "task-history-df.csv"))
        task_df = pandas.DataFrame(
            {
                "task_id": ["task1", "task2"],
                "annotation_count": [100, 200],
                "input_data_count": [2, 4],
                "inspection_comment_count": [5, 6],
                "number_of_rejections_by_inspection": [1, 2],
                "number_of_rejections_by_acceptance": [3, 4],
            }
        )
        df = Table.create_annotation_count_ratio_df(task_history_df, task_df)
        df.to_csv(out_path / "annotation-count-ratio.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_path / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(out_path / "annotation-count-ratio-df.csv")


class TestSummarizeTaskCountByTaskId:
    # task_list = [
    #     {"task_id": "A_A_01", "status": "complete", "phase":"acceptance", "phase_stage":1},
    #     {"task_id": "A_A_02", "status": "not_started", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "A_B_02", "status": "on_hold", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "abc", "status": "break", "phase":"acceptance", "phase_stage":1},
    # ]

    def test_get_task_id_prefix(self):
        assert get_task_id_prefix("A_A_01", delimiter="_") == "A_A"
        assert get_task_id_prefix("abc", delimiter="_") == "unknown"

    def test_create_task_count_summary_df(self):
        with (data_path / "task.json").open(encoding="utf-8") as f:
            task_list = json.load(f)
        df = create_task_count_summary_df(task_list, task_id_delimiter="_", task_id_groups=None)
        assert len(df) == 1
        df.iloc[0]["task_id_group"] == "sample"
