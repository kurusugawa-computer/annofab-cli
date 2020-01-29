from pathlib import Path

from annofabcli.statistics.graph import LineGraph

out_path = Path("./tests/out")
data_path = Path("./tests/data")

project_id = "12345678-abcd-1234-abcd-1234abcd5678"
graph_obj = LineGraph(str(out_path), project_id)

# class TestGraph:
#     def test_write_productivity_line_graph_for_annotator(self):
#         df = pandas.read_csv(str(data_path / "statistics/教師付作業者別-日別-情報.csv"))
#         graph_obj.write_productivity_line_graph_for_annotator(df)
#
#     def test_write_プロジェクト全体のヒストグラム(self):
#         df = pandas.read_csv(str(data_path / "statistics/task.csv"))
#         graph_obj.write_プロジェクト全体のヒストグラム(df)
