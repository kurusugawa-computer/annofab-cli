from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser

output_dir = Path("./tests/out/statistics/visualization/dataframe/task_worktime_by_phase_user")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTaskWorktimeByPhaseUser:
    obj: TaskWorktimeByPhaseUser

    @classmethod
    def setup_class(cls) -> None:
        df_worktime_ratio = pandas.read_csv(str(data_dir / "annotation-count-ratio-df.csv"))
        df_user = pandas.read_csv(str(data_dir / "user.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = TaskWorktimeByPhaseUser.from_df(
            df_worktime_ratio=df_worktime_ratio, df_user=df_user, df_task=df_task, project_id="prj1"
        )

    def test__from_df__and__to_csv(self):
        df_worktime_ratio = pandas.read_csv(str(data_dir / "annotation-count-ratio-df.csv"))
        df_user = pandas.read_csv(str(data_dir / "user.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        actual = TaskWorktimeByPhaseUser.from_df(
            df_worktime_ratio=df_worktime_ratio, df_user=df_user, df_task=df_task, project_id="prj1"
        )

        assert len(actual.df) == 5
        target_row = actual.df[
            (actual.df["task_id"] == "task1") & (actual.df["phase"] == "annotation") & (actual.df["user_id"] == "alice")
        ].iloc[0]
        assert target_row["worktime_hour"] == 2
        assert target_row["task_count"] == 1

        actual.to_csv(output_dir / "test__from_df__to_csv.csv")

    def test__from_csv__and__to_csv(self):
        actual = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        assert len(actual.df) == 5
        target_row = actual.df[
            (actual.df["task_id"] == "task1") & (actual.df["phase"] == "annotation") & (actual.df["user_id"] == "alice")
        ].iloc[0]
        assert target_row["worktime_hour"] == 2
        assert target_row["task_count"] == 1
        actual.to_csv(output_dir / "test__from_csv__and__to_csv")

    def test__merge(self):
        obj = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        actual = TaskWorktimeByPhaseUser.merge(obj, obj)
        assert len(actual.df) == 10

    def test__merge__emptyオブジェクトに対して(self):
        empty = TaskWorktimeByPhaseUser.empty()
        assert empty.is_empty()

        merged_obj = TaskWorktimeByPhaseUser.merge(empty, self.obj)
        assert len(self.obj.df) == len(merged_obj.df)
