import pandas
from pathlib import Path

from annofabcli.statistics.tsv import Tsv
from annofabcli.statistics.table import Table

out_path = Path("./tests/out")
data_path = Path("./tests/data")

project_id = "12345678-abcd-1234-abcd-1234abcd5678"
tsv_obj = Tsv(str(out_path), project_id)

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
        task_df = pandas.DataFrame({"task_id":["task1", "task2"], "annotation_count":[100,200], "input_data_count":[2,4]})
        df = Table.create_annotation_count_ratio_df(task_history_df, task_df)
        df.to_csv("/home/vagrant/Downloads/output-df2.csv")
        print(df.columns)
        print(df.iloc[0:100])


