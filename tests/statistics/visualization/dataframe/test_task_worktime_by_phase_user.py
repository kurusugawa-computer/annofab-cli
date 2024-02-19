from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser

output_dir = Path("./tests/out/statistics/visualization/dataframe/task_worktime_by_phase_user")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTaskWorktimeByPhaseUser:
    def test__from_df__and__to_csv(self):
        df_worktime_ratio = pandas.read_csv(str(data_dir / "annotation-count-ratio-df.csv"))
        df_user = pandas.read_csv(str(data_dir / "user.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        actual = TaskWorktimeByPhaseUser.from_df_wrapper(
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
        original = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        empty = TaskWorktimeByPhaseUser.empty()
        assert empty.is_empty()

        merged_obj = TaskWorktimeByPhaseUser.merge(empty, original)
        assert len(original.df) == len(merged_obj.df)

    def test__mask_user_info(self):
        obj = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        masked_obj = obj.mask_user_info(
            to_replace_for_user_id={"alice": "masked_user_id"},
            to_replace_for_username={"Alice": "masked_username"},
            to_replace_for_account_id={"alice": "masked_account_id"},
            to_replace_for_biography={"USA": "masked_biography"},
        )

        actual_first_row = masked_obj.df.iloc[0]
        assert actual_first_row["account_id"] == "masked_account_id"
        assert actual_first_row["user_id"] == "masked_user_id"
        assert actual_first_row["username"] == "masked_username"
        assert actual_first_row["biography"] == "masked_biography"
