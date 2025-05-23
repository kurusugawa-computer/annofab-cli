from pathlib import Path

from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
    ProductionVolumeColumn,
    TaskWorktimeByPhaseUser,
)

output_dir = Path("./tests/out/statistics/visualization/dataframe/productivity_per_date")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestAnnotatorProductivityPerDate:
    def test_scenario(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = AnnotatorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        obj.to_csv(output_dir / "教師付開始日ごとの教師付者の生産性.csv")
        obj.plot_production_volume_metrics("annotation_count", "アノテーション", output_dir / "折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用.html")


class TestInspectorProductivityPerDate:
    def test_scenario(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = InspectorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        obj.to_csv(output_dir / "検査開始日ごとの検査者の生産性.csv")
        obj.plot_production_volume_metrics("annotation_count", "アノテーション", output_dir / "折れ線-横軸_検査開始日-縦軸_アノテーションあたりの指標-検査者用.html")


class TestAcceptorProductivityPerDate:
    def test_scenario(self):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = AcceptorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        obj.to_csv(output_dir / "受入開始日ごとの受入者の生産性.csv")
        obj.plot_production_volume_metrics("annotation_count", "アノテーション", output_dir / "折れ線-横軸_受入開始日-縦軸_アノテーションあたりの指標-受入者用.html")
