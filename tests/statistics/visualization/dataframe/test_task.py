from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.task import Task, TaskWorktimeByPhaseUser

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTask:
    obj: Task

    @classmethod
    def setup_class(cls) -> None:
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = Task(df_task)

    def test_plot_histogram_of_worktime(self):
        self.obj.plot_histogram_of_worktime(output_dir / "ヒストグラム-作業時間.html")

    def test_plot_histogram_of_others(self):
        self.obj.plot_histogram_of_others(output_dir / "ヒストグラム.html")

    def test_empty(self):
        empty = Task.empty()
        assert empty.is_empty()

        merged_obj = Task.merge(empty, self.obj)
        assert len(self.obj.df) == len(merged_obj.df)


class TestTaskWorktimeByPhaseUser:
    obj: TaskWorktimeByPhaseUser

    @classmethod
    def setup_class(cls) -> None:
        df_worktime_ration = pandas.read_csv(str(data_dir / "annotation-count-ratio-df.csv"))
        df_user = pandas.read_csv(str(data_dir / "user.csv"))
        cls.obj = TaskWorktimeByPhaseUser.from_df(df_worktime_ration, df_user, project_id="prj1")

    def test__to_csv(self):
        self.obj.to_csv(output_dir / "task-worktime-by-user-phase.csv")

    def test_empty(self):
        empty = TaskWorktimeByPhaseUser.empty()
        assert empty.is_empty()

        merged_obj = TaskWorktimeByPhaseUser.merge(empty, self.obj)
        assert len(self.obj.df) == len(merged_obj.df)
