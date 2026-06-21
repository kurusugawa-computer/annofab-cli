from pathlib import Path

from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

output_dir = Path("./tests/out/statistics/visualization/dataframe/cumulative_productivity")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestAnnotatorCumulativeProductivity:
    def test_plot_production_volume_metrics(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv")

        obj = AnnotatorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user)
        assert len(obj.df) == 2
        obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-教師付者用.html")

    def test_plot_production_volume_metrics_with_selector(self, tmp_path: Path):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = AnnotatorCumulativeProductivity.from_df_wrapper(task_worktime_by_phase_user)
        output_file = tmp_path / "累積折れ線-横軸_生産量-教師付者用.html"
        obj.plot_production_volume_metrics_with_selector(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert '"name":"Select"' in html
        assert "xAxisList" in html
        assert "cumulative_annotation_count" in html
        assert "cumulative_input_data_count" in html
        assert "cumulative_custom_production_volume1" in html
        assert "cumulative_custom_production_volume2" in html
        assert '["input_data_count","@{input_data_count}"]' in html
        assert '["custom_production_volume1","@{custom_production_volume1}"]' in html
        assert '["custom_production_volume2","@{custom_production_volume2}"]' in html


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
