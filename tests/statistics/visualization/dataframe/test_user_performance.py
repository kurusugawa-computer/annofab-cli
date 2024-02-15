from pathlib import Path

from annofabcli.statistics.visualization.dataframe.task import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import (
    PerformanceUnit,
    UserPerformance,
    WholePerformance,
    WorktimeType,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestUserPerformance:
    obj: UserPerformance

    @classmethod
    def setup_class(cls) -> None:
        cls.obj = UserPerformance.from_csv(data_dir / "productivity-per-user2.csv")

    def test__from_df_wrapper__to_csv(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "annotation-count-ratio-df.csv")
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
        )
        assert len(actual.df) == 2
        assert actual.df[("user_id", "")][0] == "alice"
        assert actual.df[("real_actual_worktime_hour", "sum")][0] == 6
        assert actual.df[("task_count", "annotation")][0] == 2

        actual.to_csv(output_dir / "test__from_df__to_csv.csv")

    def test__from_df_wrapper__集計対象タスクが0件のとき(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "annotation-count-ratio-df-empty.csv")
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
        )
        actual.to_csv(output_dir / "test__from_df__集計対象タスクが0件のとき.csv")

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "メンバごとの生産性と品質.csv")

    def test_plot_quality(self):
        self.obj.plot_quality(output_dir / "散布図-教師付者の品質と作業量の関係.html")

    def test_plot_productivity(self):
        self.obj.plot_productivity(
            output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html",
            worktime_type=WorktimeType.ACTUAL,
            performance_unit=PerformanceUnit.ANNOTATION_COUNT,
        )
        self.obj.plot_productivity(
            output_dir / "散布図-入力データあたり作業時間と累計作業時間の関係-計測時間.html",
            worktime_type=WorktimeType.MONITORED,
            performance_unit=PerformanceUnit.INPUT_DATA_COUNT,
        )

    def test_plot_quality_and_productivity(self):
        self.obj.plot_quality_and_productivity(
            output_dir / "散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html",
            worktime_type=WorktimeType.ACTUAL,
            performance_unit=PerformanceUnit.ANNOTATION_COUNT,
        )

        self.obj.plot_quality_and_productivity(
            output_dir / "散布図-入力データあたり作業時間と品質の関係-計測時間-教師付者用.html",
            worktime_type=WorktimeType.ACTUAL,
            performance_unit=PerformanceUnit.INPUT_DATA_COUNT,
        )

    def test__get_summary(self):
        ser = self.obj.get_summary()
        assert int(ser[("task_count", "annotation")]) == 470

    def test__get_summary__emptyオブジェクトに対して(self):
        empty = UserPerformance.empty()
        assert empty.is_empty()
        summary = empty.get_summary()
        assert summary[("task_count", "annotation")] == 0
        assert summary[("monitored_worktime_hour", "annotation")] == 0
        assert summary[("actual_worktime_hour", "annotation")] == 0
        assert summary[("monitored_worktime_ratio", "annotation")] == 1


class TestWholePerformance:
    obj: WholePerformance

    @classmethod
    def setup_class(cls):
        cls.obj = WholePerformance.from_csv(data_dir / "全体の生産性と品質.csv")
        assert cls.obj.series["task_count"]["annotation"] == 1051

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "全体の生産性と品質.csv")

    def test_empty(self):
        empty = WholePerformance.empty()
        assert empty.series[("task_count", "annotation")] == 0
