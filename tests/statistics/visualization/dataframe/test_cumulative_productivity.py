from pathlib import Path

from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser

output_dir = Path("./tests/out/statistics/visualization/dataframe/cumulative_productivity")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestAnnotatorCumulativeProductivity:
    def test_plot_production_volume_metrics(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")

        obj = AnnotatorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user)
        assert len(obj.df) == 2
        obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-教師付者用.html")


class TestInspectorCumulativeProductivity:
    def test_plot_production_volume_metrics(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        obj = InspectorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user)
        assert len(obj.df) == 2
        obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-検査者用.html")


class TestAcceptorCumulativeProductivity:
    def test_plot_production_volume_metrics(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")
        obj = AcceptorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user)
        assert len(obj.df) == 1
        obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-受入者用.html")
