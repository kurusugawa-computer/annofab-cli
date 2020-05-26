from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.statistics.csv import Csv
from annofabcli.statistics.linegraph import LineGraph
from annofabcli.statistics.scatter import Scatter
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus
from annofabcli.statistics.table import Table

out_path = Path("./tests/out")
data_path = Path("./tests/data")
(out_path / "statistics").mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"

csv_obj = Csv(str(out_path), project_id)


class TestTable:
    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        task_df = pandas.DataFrame(
            {
                "task_id": ["task1", "task2"],
                "annotation_count": [100, 200],
                "input_data_count": [2, 4],
                "inspection_count": [5, 6],
                "number_of_rejections": [1, 2],
            }
        )
        df = Table.create_annotation_count_ratio_df(task_history_df, task_df)
        df.to_csv(out_path / "statistics/annotation-count-ratio.csv")

    def test_create_productivity_per_user_from_aw_time(self):
        df_task_history = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        df_labor = pandas.read_csv(str(data_path / "statistics/labor-df.csv"))
        df_worktime_ratio = pandas.read_csv(str(data_path / "statistics/annotation-count-ratio-df.csv"))
        df = Table.create_productivity_per_user_from_aw_time(df_task_history, df_labor, df_worktime_ratio)

        df.to_csv(out_path / "statistics/productivity-per-user.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        df_task = pandas.read_csv(str(data_path / "statistics/task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(out_path / "statistics/annotation-count-ratio-df.csv")

    def test_create_whole_productivity_per_date(self):
        df_task = pandas.read_csv(str(data_path / "statistics/task.csv"))
        df_labor = pandas.read_csv(str(data_path / "statistics/labor-df.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=df_labor)
        csv_obj.write_whole_productivity_per_date(df)

    def test_create_whole_productivity_per_date__labor_is_empty(self):
        df_task = pandas.read_csv(str(data_path / "statistics/task.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=pandas.DataFrame())
        csv_obj.write_whole_productivity_per_date(df)


class TestSummarizeTaskCount:
    def test_SimpleTaskStatus_from_task_status(self):
        assert SimpleTaskStatus.from_task_status(TaskStatus.ON_HOLD) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.BREAK) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.WORKING) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.NOT_STARTED) == SimpleTaskStatus.NOT_STARTED
        assert SimpleTaskStatus.from_task_status(TaskStatus.COMPLETE) == SimpleTaskStatus.COMPLETE


class TestScatter:
    scatter_obj = None

    @classmethod
    def setup_class(cls):
        cls.scatter_obj = Scatter(outdir=str(out_path / "statistics"), project_id=project_id)

    def read_productivity_per_user(self):
        productivity_per_user = pandas.read_csv(str(data_path / "statistics/productivity-per-user.csv"), header=[0, 1])
        productivity_per_user.rename(
            columns={
                "Unnamed: 0_level_1": "",
                "Unnamed: 1_level_1": "",
                "Unnamed: 2_level_1": "",
                "Unnamed: 3_level_1": "",
            },
            level=1,
            inplace=True,
        )
        return productivity_per_user

    def test_write_scatter_for_productivity_by_monitored_worktime(self):
        productivity_per_user = self.read_productivity_per_user()
        self.scatter_obj.write_scatter_for_productivity_by_monitored_worktime(productivity_per_user)

    def test_write_scatter_for_productivity_by_actual_worktime(self):
        productivity_per_user = self.read_productivity_per_user()
        self.scatter_obj.write_scatter_for_productivity_by_actual_worktime(productivity_per_user)

    def test_write_scatter_for_quality(self):
        productivity_per_user = self.read_productivity_per_user()
        self.scatter_obj.write_scatter_for_quality(productivity_per_user)


class TestLineGraph:
    line_graph_obj = None

    @classmethod
    def setup_class(cls):
        cls.line_graph_obj = LineGraph(outdir=str(out_path / "statistics"), project_id=project_id)

    def test_write_cumulative_line_graph_for_annotator(self):
        df = pandas.read_csv(str(data_path / "statistics/task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_annotator(df)
        self.line_graph_obj.write_cumulative_line_graph_for_annotator(cumulative_df)

    def test_write_cumulative_line_graph_for_inspector(self):
        df = pandas.read_csv(str(data_path / "statistics/task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_inspector(df)
        self.line_graph_obj.write_cumulative_line_graph_for_inspector(cumulative_df)

    def test_write_cumulative_line_graph_for_acceptor(self):
        df = pandas.read_csv(str(data_path / "statistics/task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_acceptor(df)
        self.line_graph_obj.write_cumulative_line_graph_for_acceptor(cumulative_df)
