from pathlib import Path

import pandas

from annofabcli.statistics.table import Table

output_dir = Path("tests/out/statistics/table")
data_dir = Path("tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"


class TestTable:
    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_dir / "task-history-df.csv"))
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
        df.to_csv(output_dir / "annotation-count-ratio.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_dir / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(output_dir / "annotation-count-ratio-df.csv")
