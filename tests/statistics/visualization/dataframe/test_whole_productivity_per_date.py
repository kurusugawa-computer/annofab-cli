from pathlib import Path
from typing import Any

import pytest

from annofabcli.statistics.visualization.dataframe import whole_productivity_per_date
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

output_dir = Path("./tests/out/statistics/visualization/dataframe/whole_productivity_per_date")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestWholeProductivityPerCompletedDate:
    main_obj: WholeProductivityPerCompletedDate
    output_dir: Path

    @classmethod
    def setup_class(cls) -> None:
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        cls.main_obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, worktime_per_date, TaskCompletionCriteria.ACCEPTANCE_COMPLETED)

        cls.output_dir = output_dir / "WholeProductivityPerCompletedDate"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

    def test__from_df_wrapper__task_completion_criteria_is_acceptance_completed(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
        )
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, worktime_per_date, TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        df_actual = obj.df
        assert df_actual["task_count"].sum() == 3
        assert df_actual[df_actual["date"] == "2019-11-14"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-15"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-25"].iloc[0]["task_count"] == 1

    def test__from_df_wrapper__task_completion_criteria_is_acceptance_reached(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
        )
        worktime_per_date = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, worktime_per_date, TaskCompletionCriteria.ACCEPTANCE_REACHED)
        df_actual = obj.df

        assert df_actual["task_count"].sum() == 3
        assert df_actual[df_actual["date"] == "2019-11-13"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-14"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-20"].iloc[0]["task_count"] == 1

    def test_from_df__df_worktime引数が空でもインスタンスを生成できることを確認する(self):
        # 完了タスクが１つもない状態で試す
        task = Task.from_csv(data_dir / "task.csv")
        obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, WorktimePerDate.empty(), TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        df_actual = obj.df

        # 日毎の完了したタスク数が一致していることの確認
        assert df_actual["task_count"].sum() == 3
        assert df_actual[df_actual["date"] == "2019-11-14"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-15"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-25"].iloc[0]["task_count"] == 1

        # df_worktimeが空なので作業時間は0であることを確認する
        assert df_actual["actual_worktime_hour"].sum() == 0
        assert df_actual["monitored_worktime_hour"].sum() == 0

    def test__to_csv(self):
        self.main_obj.to_csv(self.output_dir / "test_to_csv.csv")

    def test__plot(self):
        self.main_obj.plot(self.output_dir / "test__plot.html")

    def test__plot_cumulatively(self):
        output_file = self.output_dir / "test__plot_cumulatively.html"
        self.main_obj.plot_cumulatively(output_file)

        html = output_file.read_text(encoding="utf-8")
        assert "cumsum_task_count" in html
        assert "cumsum_input_data_count" in html
        assert "cumsum_annotation_count" in html
        assert "cumsum_custom_production_volume1" in html
        assert "cumsum_custom_production_volume2" in html

    def test__plot_cumulatively__累積作業時間グラフを先頭に表示する(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        captured: dict[str, Any] = {}

        def fake_write_bokeh_graph(bokeh_obj: Any, _output_file: Path) -> None:  # noqa: ANN401
            captured["bokeh_obj"] = bokeh_obj

        monkeypatch.setattr(whole_productivity_per_date, "write_bokeh_graph", fake_write_bokeh_graph)

        self.main_obj.plot_cumulatively(tmp_path / "test__plot_cumulatively.html")

        layout = captured["bokeh_obj"]
        assert layout.children[1].title.text == "日ごとの累積作業時間"
        production_volume_graph = layout.children[2].children[0]
        production_volume_select = layout.children[2].children[1]
        assert production_volume_graph.title.text == "日ごとの累積タスク数"
        assert production_volume_select.title == "生産量種別:"
        assert production_volume_select.options == [
            ("task_count", "タスク数"),
            ("input_data_count", "入力データ数"),
            ("annotation_count", "アノテーション数"),
            ("custom_production_volume1", "custom_生産量1"),
            ("custom_production_volume2", "custom_生産量2"),
        ]
        callback = production_volume_select.js_property_callbacks["change:value"][0]
        assert "yAxis.axis_label = selected.name;" in callback.code
        assert "yAxis.change.emit();" in callback.code
        assert "legendItem.label.value = selected.name;" in callback.code
        assert "legendItem.change.emit();" in callback.code
        hover_tool = next(tool for tool in production_volume_graph.toolbar.tools if hasattr(tool, "tooltips"))
        assert hover_tool.tooltips == [
            ("(x,y)", "($x, $y)"),
            ("date", "@{date}"),
            ("actual_worktime_hour", "@{actual_worktime_hour}"),
            ("monitored_worktime_hour", "@{monitored_worktime_hour}"),
            ("task_count", "@{task_count}"),
            ("input_data_count", "@{input_data_count}"),
            ("annotation_count", "@{annotation_count}"),
            ("custom_production_volume1", "@{custom_production_volume1}"),
            ("custom_production_volume2", "@{custom_production_volume2}"),
            ("cumsum_task_count", "@{cumsum_task_count}"),
            ("cumsum_input_data_count", "@{cumsum_input_data_count}"),
            ("cumsum_annotation_count", "@{cumsum_annotation_count}"),
            ("cumsum_custom_production_volume1", "@{cumsum_custom_production_volume1}"),
            ("cumsum_custom_production_volume2", "@{cumsum_custom_production_volume2}"),
        ]


class TestWholeProductivityPerFirstAnnotationStartedDate:
    output_dir: Path

    @classmethod
    def setup_class(cls) -> None:
        cls.output_dir = output_dir / "WholeProductivityPerFirstAnnotationStartedDate"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

    def test__from_task__task_completion_criteria_is_acceptance_completed(self):
        task = Task.from_csv(
            data_dir / "task.csv",
        )
        obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task, TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        df_actual = obj.df
        assert df_actual["task_count"].sum() == 3

    def test__from_task__task_completion_criteria_is_acceptance_reached(cls):
        task = Task.from_csv(
            data_dir / "task.csv",
        )
        obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task, TaskCompletionCriteria.ACCEPTANCE_REACHED)
        df_actual = obj.df
        assert df_actual["task_count"].sum() == 4

    def test__from_task__and__to_csv(self):
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task, TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        obj.to_csv(self.output_dir / "test__from_task__and__to_csv.csv")

    def test__from_task__and__plot(self):
        task = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task, TaskCompletionCriteria.ACCEPTANCE_COMPLETED)
        obj.plot(self.output_dir / "test__from_task__and__plot.html")
