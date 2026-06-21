from pathlib import Path

import pandas

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

    def test__get_worktime_type_list_for_plot__実績時間をデフォルトにする(self) -> None:
        assert self.obj._get_worktime_type_list_for_plot()[0] == WorktimeType.ACTUAL

    def test__get_production_volume_list_for_plot__アノテーションをデフォルトにする(self) -> None:
        assert self.obj._get_production_volume_list_for_plot()[0].value == "annotation_count"

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

    def test_plot_productivity__find_userにはプロットされたユーザーだけを表示する(self, tmp_path: Path) -> None:
        df = self.obj.df.copy()
        not_plotted_user_df = df.iloc[[0]].copy()
        not_plotted_user_df[("user_id", "")] = "not_plotted"
        not_plotted_user_df[("username", "")] = "not_plotted"
        for phase in self.obj.phase_list:
            not_plotted_user_df[("actual_worktime_hour", phase)] = pandas.NA
            not_plotted_user_df[("actual_worktime_hour/annotation_count", phase)] = pandas.NA

        obj = UserPerformance(
            pandas.concat([df, not_plotted_user_df], ignore_index=True),
            self.obj.task_completion_criteria,
            custom_production_volume_list=self.obj.custom_production_volume_list,
        )

        output_file = tmp_path / "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html"
        obj.plot_productivity(output_file, worktime_type=WorktimeType.ACTUAL, production_volume_column="annotation_count")

        html = output_file.read_text(encoding="utf-8")
        assert "AC:AC" in html
        assert "not_plotted:not_plotted" not in html

    def test_plot_productivity_with_worktime_type_selector(self, tmp_path: Path) -> None:
        output_file = tmp_path / "散布図-アノテーションあたり作業時間と累計作業時間の関係.html"
        self.obj.plot_productivity_with_worktime_type_selector(
            output_file,
            production_volume_column="annotation_count",
        )

        html = output_file.read_text(encoding="utf-8")
        assert "monitored" in html
        assert "actual" in html

    def test_plot_productivity_with_selectors(self, tmp_path: Path) -> None:
        output_file = tmp_path / "散布図-生産量あたり作業時間と累計作業時間の関係.html"
        self.obj.plot_productivity_with_selectors(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert "monitored" in html
        assert "actual" in html
        assert "annotation_count" in html
        assert "input_data_count" in html

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

    def test_plot_quality_and_productivity_with_worktime_type_selector(self, tmp_path: Path) -> None:
        output_file = tmp_path / "散布図-アノテーションあたり作業時間と品質の関係-教師付者用.html"
        self.obj.plot_quality_and_productivity_with_worktime_type_selector(
            output_file,
            production_volume_column="annotation_count",
        )

        html = output_file.read_text(encoding="utf-8")
        assert "monitored" in html
        assert "actual" in html

    def test_plot_quality_and_productivity_with_selectors(self, tmp_path: Path) -> None:
        output_file = tmp_path / "散布図-生産量あたり作業時間と品質の関係-教師付者用.html"
        self.obj.plot_quality_and_productivity_with_selectors(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert "monitored" in html
        assert "actual" in html
        assert "annotation_count" in html
        assert "input_data_count" in html
