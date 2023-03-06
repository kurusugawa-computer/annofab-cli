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
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        assert len(df) == 10
