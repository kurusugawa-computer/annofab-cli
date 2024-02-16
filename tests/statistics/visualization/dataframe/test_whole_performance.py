from pathlib import Path

from annofabcli.statistics.visualization.dataframe.task import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.whole_performance import (
    WholePerformance,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

output_dir = Path("./tests/out/statistics/visualization/dataframe/whole_performance")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestWholePerformance:
    obj: WholePerformance

    @classmethod
    def setup_class(cls) -> None:
        cls.obj = WholePerformance.from_csv(data_dir / "全体の生産性と品質.csv")
        assert cls.obj.series["task_count"]["annotation"] == 1051

    def test__from_df_wrapper__to_csv(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "annotation-count-ratio-df.csv")
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = WholePerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
        )
        actual.to_csv(output_dir / "test__from_df__to_csv.csv")

        assert actual.series[("real_monitored_worktime_hour", "sum")] == 8
        assert actual.series[("task_count", "annotation")] == 2
        assert actual.series[("working_user_count", "annotation")] == 2

    def test__empty__to_csv(self):
        empty = WholePerformance.empty()
        empty.to_csv(output_dir / "test__from_df__to_csv.csv")
        assert empty.series[("real_monitored_worktime_hour", "sum")] == 0
        assert empty.series[("task_count", "annotation")] == 0

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "全体の生産性と品質.csv")
