from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.task import Task

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)

# 出力できることを確認する


class TestAnnotatorCumulativeProductivity:
    obj: AnnotatorCumulativeProductivity

    @classmethod
    def setup_class(cls):
        task = Task.from_csv(data_dir / "task.csv")
        cls.obj = AnnotatorCumulativeProductivity.from_task(task)

    def test_plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics(
            "annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-教師付者用.html"
        )


class TestInspectorCumulativeProductivity:
    obj: InspectorCumulativeProductivity

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = InspectorCumulativeProductivity(df_task)

    def test_plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-検査者用.html")


class TestAcceptorCumulativeProductivity:
    obj: AcceptorCumulativeProductivity

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = AcceptorCumulativeProductivity(df_task)

    def test_plot_production_volume_metrics(self):
        self.obj.plot_production_volume_metrics("annotation_count", "アノテーション数", output_dir / "累積折れ線-横軸_アノテーション数-受入者用.html")
