import json
from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.csv import Csv
from annofabcli.statistics.linegraph import LineGraph
from annofabcli.statistics.scatter import Scatter
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus
from annofabcli.statistics.summarize_task_count_by_task_id import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table

out_path = Path("./tests/out/statistics")
data_path = Path("./tests/data/statistics")
out_path.mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"


class TestTable:
    @classmethod
    def setup_class(cls):
        cls.csv_obj = Csv(str(out_path))

    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_path / "task-history-df.csv"))
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
        df.to_csv(out_path / "annotation-count-ratio.csv")

    def test_create_productivity_per_user_from_aw_time(self):
        df_task_history = pandas.read_csv(str(data_path / "task-history-df.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df_worktime_ratio = pandas.read_csv(str(data_path / "annotation-count-ratio-df.csv"))
        df = Table.create_productivity_per_user_from_aw_time(df_task_history, df_labor, df_worktime_ratio)

        df.to_csv(out_path / "productivity-per-user.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_path / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(out_path / "annotation-count-ratio-df.csv")

    def test_create_whole_productivity_per_date(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=df_labor)
        self.csv_obj.write_whole_productivity_per_date(df)

    def test_create_whole_productivity_per_date2(self):
        # 完了タスクが１つもない状態で試す
        df_task = pandas.read_csv(str(data_path / "only-working-task.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=df_labor)
        self.csv_obj.write_whole_productivity_per_date(df)

    def test_create_whole_productivity_per_date__labor_is_empty(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=pandas.DataFrame())
        self.csv_obj.write_whole_productivity_per_date(df)

    def test_merge_whole_productivity_per_date(self):
        df1 = pandas.read_csv(str(data_path / "productivity-per-date.csv"))
        df2 = pandas.read_csv(str(data_path / "productivity-per-date2.csv"))
        sum_df = Table.merge_whole_productivity_per_date(df1, df2)
        print(sum_df)
        sum_df.to_csv(out_path / "merge-productivity-per-date.csv")


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
        cls.scatter_obj = Scatter(outdir=str(out_path))

    def test_write_scatter_for_productivity_by_monitored_worktime(self):
        productivity_per_user = read_multiheader_csv(str(data_path / "productivity-per-user2.csv"))
        self.scatter_obj.write_scatter_for_productivity_by_monitored_worktime(productivity_per_user)

    def test_write_scatter_for_productivity_by_actual_worktime(self):
        productivity_per_user = read_multiheader_csv(str(data_path / "productivity-per-user2.csv"))
        self.scatter_obj.write_scatter_for_productivity_by_actual_worktime(productivity_per_user)

    def test_write_scatter_for_quality(self):
        productivity_per_user = read_multiheader_csv(str(data_path / "productivity-per-user2.csv"))
        self.scatter_obj.write_scatter_for_quality(productivity_per_user)

    def test_write_scatter_for_productivity_by_actual_worktime_and_quality(self):
        productivity_per_user = read_multiheader_csv(str(data_path / "productivity-per-user2.csv"))
        self.scatter_obj.write_scatter_for_productivity_by_actual_worktime_and_quality(productivity_per_user)


class TestCsv:
    csv_obj = None

    @classmethod
    def setup_class(cls):
        cls.csv_obj = Csv(outdir=str(out_path))

    def test_write_whole_productivity(self):
        productivity_per_user = read_multiheader_csv(str(data_path / "productivity-per-user2.csv"))
        self.csv_obj.write_whole_productivity(productivity_per_user)


class TestLineGraph:
    line_graph_obj = None

    @classmethod
    def setup_class(cls):
        cls.line_graph_obj = LineGraph(outdir=str(out_path))

    def test_write_cumulative_line_graph_for_annotator(self):
        df = pandas.read_csv(str(data_path / "task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_annotator(df)
        self.line_graph_obj.write_cumulative_line_graph_for_annotator(cumulative_df)

    def test_write_cumulative_line_graph_for_inspector(self):
        df = pandas.read_csv(str(data_path / "task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_inspector(df)
        self.line_graph_obj.write_cumulative_line_graph_for_inspector(cumulative_df)

    def test_write_cumulative_line_graph_for_acceptor(self):
        df = pandas.read_csv(str(data_path / "task.csv"))
        cumulative_df = Table.create_cumulative_df_by_first_acceptor(df)
        self.line_graph_obj.write_cumulative_line_graph_for_acceptor(cumulative_df)

    def test_write_cumulative_line_graph_overall(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_cumulative = Table.create_cumulative_df_overall(df_task)
        self.line_graph_obj.write_cumulative_line_graph_overall(df_cumulative)

    def test_write_whole_productivity_line_graph(self):
        df = pandas.read_csv(str(data_path / "productivity-per-date3.csv"))
        self.line_graph_obj.write_whole_productivity_line_graph(df)

    def test_write_whole_cumulative_line_graph(self):
        df = pandas.read_csv(str(data_path / "productivity-per-date3.csv"))
        self.line_graph_obj.write_whole_cumulative_line_graph(df)


class TestSummarizeTaskCountByTaskId:
    # task_list = [
    #     {"task_id": "A_A_01", "status": "complete", "phase":"acceptance", "phase_stage":1},
    #     {"task_id": "A_A_02", "status": "not_started", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "A_B_02", "status": "on_hold", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "abc", "status": "break", "phase":"acceptance", "phase_stage":1},
    # ]

    def test_get_task_id_prefix(self):
        assert get_task_id_prefix("A_A_01") == "A_A"
        assert get_task_id_prefix("abc") == "unknown"

    def test_create_task_count_summary_df(self):
        with (data_path / "task.json").open() as f:
            task_list = json.load(f)
        df = create_task_count_summary_df(task_list, delimiter="_")
