from pathlib import Path

import pandas

from annofabcli.statistics.table import Table

output_dir = Path("tests/out/statistics/table")
data_dir = Path("tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTable:
    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_dir / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        actual = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        assert len(actual) == 10

        actual2 = actual.set_index(["task_id", "phase", "phase_stage", "account_id"])
        assert actual2.loc["task1", "annotation", 1, "alice"].to_dict() == {
            "worktime_hour": 2,
            "task_count": 1.0,
            "annotation_count": 41.0,
            "input_data_count": 10.0,
            "pointed_out_inspection_comment_count": 9,
            "rejected_count": 1,
        }

        assert actual2.loc["task1", "inspection", 1, "bob"].to_dict() == {
            "worktime_hour": 0.5,
            "task_count": 0.5,
            "annotation_count": 20.5,
            "input_data_count": 5,
            "pointed_out_inspection_comment_count": 0.0,
            "rejected_count": 0.0,
        }
