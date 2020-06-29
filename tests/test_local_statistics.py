import json
from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.statistics.csv import Csv
from annofabcli.statistics.linegraph import LineGraph
from annofabcli.statistics.list_submitted_task_count import to_formatted_dataframe
from annofabcli.statistics.scatter import Scatter
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus
from annofabcli.statistics.summarize_task_count_by_task_id import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table

out_path = Path("./tests/out/statistics")
data_path = Path("./tests/data/statistics")
out_path.mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"

csv_obj = Csv(str(out_path), project_id[0:8])


class TestTable:
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
        csv_obj.write_whole_productivity_per_date(df)

    def test_create_whole_productivity_per_date2(self):
        # 完了タスクが１つもない状態で試す
        df_task = pandas.read_csv(str(data_path / "only-working-task.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df = Table.create_whole_productivity_per_date(df_task=df_task, df_labor=df_labor)
        csv_obj.write_whole_productivity_per_date(df)

    def test_create_whole_productivity_per_date__labor_is_empty(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
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
        cls.scatter_obj = Scatter(outdir=str(out_path), filename_prefix=project_id[0:8])

    def read_productivity_per_user(self):
        productivity_per_user = pandas.read_csv(str(data_path / "productivity-per-user.csv"), header=[0, 1])
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
        cls.line_graph_obj = LineGraph(outdir=str(out_path), filename_prefix=project_id[0:8])

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


class TestListSubmittedTaskCount:
    def test_to_formatted_dataframe(self):
        data_list = [
            {
                "date": "2020-04-01",
                "phase": "annotation",
                "account_id": "alice",
                "user_id": "alice",
                "username": "Alice",
                "biography": "U.K.",
                "task_count": 10,
            },
            {
                "date": "2020-04-01",
                "phase": "acceptance",
                "account_id": "alice",
                "user_id": "alice",
                "username": "Alice",
                "biography": "U.K.",
                "task_count": 20,
            },
            {
                "date": "2020-04-01",
                "phase": "annotation",
                "account_id": "bob",
                "user_id": "bob",
                "username": "Bob",
                "biography": None,
                "task_count": 30,
            },
        ]
        df = pandas.DataFrame(data_list)

        df2 = to_formatted_dataframe(df)
        print()
        print(df2)
        df2.to_csv("hoge.csv")
