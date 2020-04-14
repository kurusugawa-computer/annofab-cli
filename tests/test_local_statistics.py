from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.statistics.csv import Csv
from annofabcli.statistics.scatter import Scatter
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus
from annofabcli.statistics.table import Table

out_path = Path("./tests/out")
data_path = Path("./tests/data")

project_id = "12345678-abcd-1234-abcd-1234abcd5678"
tsv_obj = Csv(str(out_path), project_id)

# class TestGraph:
#     def test_write_productivity_line_graph_for_annotator(self):
#         df = pandas.read_csv(str(data_path / "statistics/教師付作業者別-日別-情報.csv"))
#         graph_obj.write_productivity_line_graph_for_annotator(df)
#
#     def test_write_プロジェクト全体のヒストグラム(self):
#         df = pandas.read_csv(str(data_path / "statistics/task.csv"))
#         graph_obj.write_プロジェクト全体のヒストグラム(df)


class TestTable:
    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        # task_df = pandas.read_csv(str(data_path / "statistics/タスクlist.csv"))
        task_df = pandas.DataFrame(
            {
                "task_id": ["task1", "task2"],
                "annotation_count": [100, 200],
                "input_data_count": [2, 4],
                "inspection_count": [5, 6],
            }
        )
        df = Table.create_annotation_count_ratio_df(task_history_df, task_df)
        df.to_csv(out_path / "annotation-count-ratio.csv")

    def test_create_productivity_per_user_from_aw_time(self):
        df_task_history = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        df_labor = pandas.read_csv(str(data_path / "statistics/labor-df.csv"))
        df_worktime_ratio = pandas.read_csv(str(data_path / "statistics/annotation-count-ratio-df.csv"))
        df = Table.create_productivity_per_user_from_aw_time(df_task_history, df_labor, df_worktime_ratio)

        df.to_csv(out_path / "productivity-per-user.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_path / "statistics/task-history-df.csv"))
        df_task = pandas.read_csv(str(data_path / "statistics/task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(out_path / "annotation-count-ratio-df.csv")


class TestSummarizeTaskCount:
    def test_SimpleTaskStatus_from_task_status(self):
        assert SimpleTaskStatus.from_task_status(TaskStatus.ON_HOLD) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.BREAK) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.WORKING) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.NOT_STARTED) == SimpleTaskStatus.NOT_STARTED
        assert SimpleTaskStatus.from_task_status(TaskStatus.COMPLETE) == SimpleTaskStatus.COMPLETE


class TestScatter:
    scatter_obj = None

    import logging

    logging_formatter = "%(levelname)-8s : %(asctime)s : %(filename)s : %(name)s : %(funcName)s : %(message)s"
    logging.basicConfig(format=logging_formatter)
    logging.getLogger("bokeh").setLevel(level=logging.DEBUG)

    @classmethod
    def setup_class(cls):
        cls.scatter_obj = Scatter(outdir=str(out_path / "statistics"), project_id=project_id)

    def test_write_scatter_for_productivity(self):
        productivity_per_user = pandas.read_csv(str(data_path / "statistics/productivity-per-user.csv"), header=[0, 1])
        productivity_per_user.rename(
            columns={"Unnamed: 0_level_1": "", "Unnamed: 1_level_1": "", "Unnamed: 2_level_1": ""},
            level=1,
            inplace=True,
        )
        self.scatter_obj.write_scatter_for_productivity(productivity_per_user)
