from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)

# 出力できることを確認する


class TestAnnotatorProductivityPerDate:
    obj: AnnotatorProductivityPerDate

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.obj = AnnotatorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "教師付開始日ごとの教師付者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(output_dir / "折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(output_dir / "折れ線-横軸_教師付開始日-縦軸_入力データあたりの指標-教師付者用.html")


class TestInspectorProductivityPerDate:
    obj: InspectorProductivityPerDate

    @classmethod
    def setup_class(cls):

        df_task = pandas.read_csv(str(data_dir / "task.csv"))

        cls.obj = InspectorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "検査開始日ごとの検査者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(output_dir / "折れ線-横軸_検査開始日-縦軸_アノテーションあたりの指標-検査者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(output_dir / "折れ線-横軸_検査開始日-縦軸_入力データあたりの指標-検査者用.html")


class TestAcceptorProductivityPerDate:
    obj: AcceptorProductivityPerDate

    @classmethod
    def setup_class(cls):

        df_task = pandas.read_csv(str(data_dir / "task.csv"))

        cls.obj = AcceptorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "受入開始日ごとの受入者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(output_dir / "折れ線-横軸_受入開始日-縦軸_アノテーションあたりの指標-受入者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(output_dir / "折れ線-横軸_受入開始日-縦軸_入力データあたりの指標-受入者用.html")
