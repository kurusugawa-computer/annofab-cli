from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_history import TaskHistory
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user import User
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

output_dir = Path("./tests/out/statistics/visualization/dataframe/task_worktime_by_phase_user")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTaskWorktimeByPhaseUser:
    def test__from_df__and__to_csv(self):
        task_history = TaskHistory(pandas.read_csv(str(data_dir / "task-history-df.csv")))
        user = User(pandas.read_csv(str(data_dir / "user.csv")))
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        actual = TaskWorktimeByPhaseUser.from_df_wrapper(task_history=task_history, user=user, task=task, project_id="prj1")
        assert "custom_production_volume1" in actual.columns
        assert "custom_production_volume2" in actual.columns
        assert len(actual.df) == 10
        target_row = actual.df[(actual.df["task_id"] == "task1") & (actual.df["phase"] == "annotation") & (actual.df["user_id"] == "alice")].iloc[0]
        assert target_row["worktime_hour"] == 2
        assert target_row["task_count"] == 1

        actual.to_csv(output_dir / "test__from_df__to_csv.csv")

    def test__from_csv__and__to_csv(self):
        actual = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        assert len(actual.df) == 5
        target_row = actual.df[(actual.df["task_id"] == "task1") & (actual.df["phase"] == "annotation") & (actual.df["user_id"] == "alice")].iloc[0]
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

    def test___create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_dir / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        actual = TaskWorktimeByPhaseUser._create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history, custom_production_volume_columns=None)
        assert len(actual) == 10

        actual2 = actual.set_index(["task_id", "phase", "phase_stage", "account_id"])
        assert actual2.loc["task1", "annotation", 1, "alice"].to_dict() == {
            "worktime_hour": 2,
            "task_count": 1.0,
            "annotation_count": 41.0,
            "input_data_count": 10.0,
            "pointed_out_inspection_comment_count": 9,
            "rejected_count": 1,
            "started_datetime": "2024-10-25T11:00:00.000+09:00",
        }

        assert actual2.loc["task1", "inspection", 1, "bob"].to_dict() == {
            "worktime_hour": 0.5,
            "task_count": 0.5,
            "annotation_count": 20.5,
            "input_data_count": 5,
            "pointed_out_inspection_comment_count": 0.0,
            "rejected_count": 0.0,
            "started_datetime": "2024-10-26T11:00:00.000+09:00",
        }
