from pathlib import Path

from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
    ProductionVolumeColumn,
    Task,
)

output_dir = Path("./tests/out/statistics/visualization/dataframe/productivity_per_date")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)

# 出力できることを確認する


class TestAnnotatorProductivityPerDate:
    obj: AnnotatorProductivityPerDate

    @classmethod
    def setup_class(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        cls.obj = AnnotatorProductivityPerDate.from_task(task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "教師付開始日ごとの教師付者の生産性.csv")

    def test__plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics(
            "annotation_count", "アノテーション", output_dir / "折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用.html"
        )


class TestInspectorProductivityPerDate:
    obj: InspectorProductivityPerDate

    @classmethod
    def setup_class(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        cls.obj = InspectorProductivityPerDate.from_task(task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "検査開始日ごとの検査者の生産性.csv")

    def test__plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics(
            "annotation_count", "アノテーション", output_dir / "折れ線-横軸_検査開始日-縦軸_アノテーションあたりの指標-検査者用.html"
        )


class TestAcceptorProductivityPerDate:
    obj: AcceptorProductivityPerDate

    @classmethod
    def setup_class(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )

        cls.obj = AcceptorProductivityPerDate.from_task(task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "受入開始日ごとの受入者の生産性.csv")

    def test__plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics(
            "annotation_count", "アノテーション", output_dir / "折れ線-横軸_受入開始日-縦軸_アノテーションあたりの指標-受入者用.html"
        )
