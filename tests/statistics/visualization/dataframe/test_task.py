from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.task import Task

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTask:
    obj: Task

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = Task(df_task)

    def test_plot_histogram_of_worktime(self):
        self.obj.plot_histogram_of_worktime(output_dir / "ヒストグラム-作業時間.html")

    def test_plot_histogram_of_others(self):
        self.obj.plot_histogram_of_others(output_dir / "ヒストグラム.html")
