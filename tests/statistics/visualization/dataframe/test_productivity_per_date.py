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

    def test_plot_production_volume_metrics_with_selector(self, tmp_path: Path):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = AnnotatorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        output_file = tmp_path / "折れ線-横軸_教師付開始日-縦軸_生産量単位の指標-教師付者用.html"
        obj.plot_production_volume_metrics_with_selector(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert '"name":"Select"' in html
        assert "yColumnByValue" in html
        assert "annotation_worktime_minute/input_data_count" in html
        assert "annotation_worktime_minute/custom_production_volume1" in html
        assert "inspection_comment_count/custom_production_volume2" in html

    def test_create_line_graph_list_for_production_volume_selector(self):
        production_volume = ProductionVolumeColumn("annotation_count", "アノテーション")
        total_worktime_tooltip_columns = [
            "annotation_worktime_hour",
            "annotation_count",
        ]
        production_volume_worktime_tooltip_columns = [
            *total_worktime_tooltip_columns,
            "annotation_worktime_minute/annotation_count",
        ]
        inspection_comment_tooltip_columns = [
            *total_worktime_tooltip_columns,
            "inspection_comment_count",
            "inspection_comment_count/annotation_count",
        ]

        line_graph_list = AnnotatorProductivityPerDate._create_line_graph_list_for_production_volume_selector(
            default_production_volume=production_volume,
            total_worktime_tooltip_columns=total_worktime_tooltip_columns,
            production_volume_worktime_tooltip_columns=production_volume_worktime_tooltip_columns,
            inspection_comment_tooltip_columns=inspection_comment_tooltip_columns,
            x_axis_label="教師付開始日",
        )

        assert line_graph_list[0].tooltip_columns is not None
        assert "annotation_worktime_minute/annotation_count" not in line_graph_list[0].tooltip_columns

        for line_graph in line_graph_list[1:3]:
            assert line_graph.tooltip_columns is not None
            assert "annotation_worktime_minute/annotation_count" in line_graph.tooltip_columns

        for line_graph in line_graph_list[:3]:
            assert line_graph.tooltip_columns is not None
            assert "inspection_comment_count" not in line_graph.tooltip_columns
            assert "inspection_comment_count/annotation_count" not in line_graph.tooltip_columns

        for line_graph in line_graph_list[3:]:
            assert line_graph.tooltip_columns is not None
            assert "annotation_worktime_minute/annotation_count" not in line_graph.tooltip_columns
            assert "inspection_comment_count" in line_graph.tooltip_columns
            assert "inspection_comment_count/annotation_count" in line_graph.tooltip_columns


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

    def test_plot_production_volume_metrics_with_selector(self, tmp_path: Path):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = InspectorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        output_file = tmp_path / "折れ線-横軸_検査開始日-縦軸_生産量単位の指標-検査者用.html"
        obj.plot_production_volume_metrics_with_selector(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert '"name":"Select"' in html
        assert "yColumnByValue" in html
        assert "inspection_worktime_minute/input_data_count" in html
        assert "inspection_worktime_minute/custom_production_volume1" in html


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

    def test_plot_production_volume_metrics_with_selector(self, tmp_path: Path):
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(
            data_dir / "task-worktime-by-user-phase.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        obj = AcceptorProductivityPerDate.from_df_wrapper(task_worktime_by_phase_user)
        output_file = tmp_path / "折れ線-横軸_受入開始日-縦軸_生産量単位の指標-受入者用.html"
        obj.plot_production_volume_metrics_with_selector(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert '"name":"Select"' in html
        assert "yColumnByValue" in html
        assert "acceptance_worktime_minute/input_data_count" in html
        assert "acceptance_worktime_minute/custom_production_volume1" in html
