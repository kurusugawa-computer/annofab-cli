from pathlib import Path

import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.whole_performance import (
    WholePerformance,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

output_dir = Path("./tests/out/statistics/visualization/dataframe/whole_performance")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)

custom_production_volume_list = [
    ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
    ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
]


class TestWholePerformance:
    def test__from_df_wrapper__to_csv(self):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")

        actual = WholePerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
            task=task,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )
        actual.to_csv(output_dir / "test__from_df__to_csv.csv")

        assert actual.series[("real_monitored_worktime_hour", "sum")] == 8
        assert actual.series[("task_count", "annotation")] == 2
        assert actual.series[("working_user_count", "annotation")] == 2
        assert actual.series[("monitored_worktime_hour/task_count", "annotation")] == pytest.approx(
            actual.series[("monitored_worktime_hour", "annotation")] / actual.series[("task_count", "annotation")]
        )
        assert actual.series[("actual_worktime_hour/task_count", "annotation")] == pytest.approx(actual.series[("actual_worktime_hour", "annotation")] / actual.series[("task_count", "annotation")])
        assert actual.series[("monitored_worktime_hour/task_count__lastweek", "annotation")] == pytest.approx(2)
        assert actual.series[("lastweek_start_date", "")] == "2019-11-20"
        assert actual.series[("lastweek_end_date", "")] == "2019-11-26"
        assert actual.series[("task_count__lastweek", "annotation")] == pytest.approx(1)
        assert actual.series[("input_data_count__lastweek", "annotation")] == pytest.approx(2)
        assert actual.series[("annotation_count__lastweek", "annotation")] == pytest.approx(100)
        assert actual.series[("custom_production_volume1__lastweek", "annotation")] == pytest.approx(10)
        assert actual.series[("custom_production_volume2__lastweek", "annotation")] == pytest.approx(20)
        assert actual.series[("monitored_worktime_hour/input_data_count__lastweek", "annotation")] == pytest.approx(1)
        assert actual.series[("monitored_worktime_hour/annotation_count__lastweek", "annotation")] == pytest.approx(0.02)
        assert actual.series[("monitored_worktime_hour/custom_production_volume1__lastweek", "annotation")] == pytest.approx(0.2)
        assert actual.series[("monitored_worktime_hour/custom_production_volume2__lastweek", "annotation")] == pytest.approx(0.1)
        assert actual.series[("actual_worktime_hour/task_count__lastweek", "annotation")] == pytest.approx(
            actual.series[("monitored_worktime_hour/task_count__lastweek", "annotation")] / actual.series[("real_monitored_worktime_hour/real_actual_worktime_hour", "sum")]
        )

    def test__empty__to_csv(self):
        empty = WholePerformance.empty(TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        empty.to_csv(output_dir / "test__empty__to_csv.csv")
        assert empty.series[("real_monitored_worktime_hour", "sum")] == 0
        assert empty.series[("task_count", "annotation")] == 0
        assert pandas.isna(empty.series[("lastweek_start_date", "")])
        assert pandas.isna(empty.series[("lastweek_end_date", "")])
        assert pandas.isna(empty.series[("task_count__lastweek", "annotation")])
        assert pandas.isna(empty.series[("monitored_worktime_hour/task_count__lastweek", "annotation")])

    def test__from_csv__to_csv(self):
        actual = WholePerformance.from_csv(data_dir / "全体の生産性と品質.csv", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)

        assert actual.series["task_count"]["annotation"] == 110.0
        assert pandas.isna(actual.series[("lastweek_start_date", "")])

    def test___create_all_user_performance(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "worktime-per-date.csv")
        actual = WholePerformance._create_all_user_performance(
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            worktime_per_date=worktime_per_date,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )
        assert len(actual.df) == 1
