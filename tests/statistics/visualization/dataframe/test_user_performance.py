from pathlib import Path

from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import (
    UserPerformance,
    WorktimeType,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

output_dir = Path("./tests/out/statistics/visualization/dataframe/user_perforamance")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestUserPerformance:
    obj: UserPerformance

    @classmethod
    def setup_class(cls) -> None:
        cls.obj = UserPerformance.from_csv(data_dir / "productivity-per-user2.csv", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)

    def test__from_df_wrapper__to_csv(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
            ],
        )
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )
        actual.to_csv(output_dir / "test__from_df__to_csv.csv")
        assert len(actual.df) == 2
        assert actual.df[("user_id", "")][0] == "alice"
        assert actual.df[("real_actual_worktime_hour", "sum")][0] == 6
        assert actual.df[("task_count", "annotation")][0] == 1

    def test__from_df_wrapper__集計対象タスクが0件のとき(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.empty()
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )
        actual.to_csv(output_dir / "test__from_df__集計対象タスクが0件のとき.csv")
        assert len(actual.df) == 2
        assert actual.df[("user_id", "")][0] == "alice"
        assert actual.df[("real_actual_worktime_hour", "sum")][0] == 6
        assert actual.df[("task_count", "annotation")][0] == 0

    def test__from_df_wrapper__task_completion_criteria_is_acceptance_reached(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
            ],
        )
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_REACHED,
        )
        assert ("task_count", "acceptance") not in actual.df.columns

    def test___create_df_working_period(self) -> None:
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")
        df_actual = UserPerformance._create_df_working_period(worktime_per_date)
        assert df_actual[("last_working_date", "")].loc["alice"] == "2021-11-02"
        assert df_actual[("working_days", "")].loc["bob"] == 1
        assert df_actual[("last_working_date", "acceptance")].loc["bob"] == "2021-11-01"
        assert df_actual[("working_days", "acceptance")].loc["bob"] == 1

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "メンバごとの生産性と品質.csv")

    def test_plot_quality(self):
        self.obj.plot_quality(output_dir / "散布図-教師付者の品質と作業量の関係.html")

    def test_plot_productivity__アノテーションあたり実績時間(self) -> None:
        self.obj.plot_productivity(
            output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html",
            worktime_type=WorktimeType.ACTUAL,
            production_volume_column="annotation_count",
        )

    def test_plot_productivity__入力データあたり計測時間(self) -> None:
        self.obj.plot_productivity(
            output_dir / "散布図-入力データあたり作業時間と累計作業時間の関係-計測時間.html",
            worktime_type=WorktimeType.MONITORED,
            production_volume_column="input_data_count",
        )

    def test_plot_quality_and_productivity__アノテーションあたり実績時間(self) -> None:
        self.obj.plot_quality_and_productivity(
            output_dir / "散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html",
            worktime_type=WorktimeType.ACTUAL,
            production_volume_column="annotation_count",
        )

    def test_plot_quality_and_productivity__入力データあたり計測時間(self) -> None:
        self.obj.plot_quality_and_productivity(
            output_dir / "散布図-入力データあたり作業時間と品質の関係-計測時間-教師付者用.html",
            worktime_type=WorktimeType.ACTUAL,
            production_volume_column="input_data_count",
        )
