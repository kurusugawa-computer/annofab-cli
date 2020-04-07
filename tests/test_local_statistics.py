from pathlib import Path

import pandas

from annofabcli.statistics.csv import Csv
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
        df.to_csv(out_path / "annotation_count_ratio.csv")

    def test_create_productivity_from_aw_time(self):
        df_task_history = pandas.read_csv("/home/vagrant/Downloads/hoge/21292667-タスク履歴list.csv")
        df_labor = pandas.read_csv("/home/vagrant/Downloads/hoge/21292667-労務管理list.csv")
        df_worktime_ratio = pandas.read_csv("/home/vagrant/Downloads/hoge/タスク内の作業時間の比率.csv")
        df = Table.create_productivity_from_aw_time(df_task_history, df_labor, df_worktime_ratio)
        print(df)
        print(df.columns)

        df.to_csv("hogehoge.csv")
        # df.to_csv(out_path / "annotation_count_ratio.csv")
