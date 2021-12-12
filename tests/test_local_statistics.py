import json
from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.common.utils import read_multiheader_csv
from annofabcli.statistics.csv import Csv, write_summarise_whole_performance_csv
from annofabcli.statistics.linegraph import LineGraph
from annofabcli.statistics.scatter import Scatter
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus, get_step_for_current_phase
from annofabcli.statistics.summarize_task_count_by_task_id import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)

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


class TestSummarizeTaskCount:
    def test_SimpleTaskStatus_from_task_status(self):
        assert SimpleTaskStatus.from_task_status(TaskStatus.ON_HOLD) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.BREAK) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.WORKING) == SimpleTaskStatus.WORKING_BREAK_HOLD
        assert SimpleTaskStatus.from_task_status(TaskStatus.NOT_STARTED) == SimpleTaskStatus.NOT_STARTED
        assert SimpleTaskStatus.from_task_status(TaskStatus.COMPLETE) == SimpleTaskStatus.COMPLETE

    def test_get_step_for_current_phase(self):
        task = {
            "phase": "annotation",
            "phase_stage": 1,
            "status": "not_started",
            "account_id": "account1",
            "histories_by_phase": [
                {"account_id": "account1", "phase": "annotation", "phase_stage": 1, "worked": False}
            ],
            "work_time_span": 0,
        }
        assert get_step_for_current_phase(task, number_of_inspections=1) == 1


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

    def test_write_summarise_whole_performance_csv(self):
        csv_path_list = [data_path / "全体の生産性と品質.csv"]
        df = write_summarise_whole_performance_csv(csv_path_list, output_path=out_path / "プロジェクごとの生産性と品質.csv")
        print(df)


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


class TestWholeProductivityPerFirstAnnotationStartedDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

    def test_create(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = WholeProductivityPerFirstAnnotationStartedDate.create(df_task)
        print(df)
        df.to_csv(self.output_dir / "out.csv", index=False)

    def test_plot(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = WholeProductivityPerFirstAnnotationStartedDate.create(df_task)

        WholeProductivityPerFirstAnnotationStartedDate.plot(df, self.output_dir / "教師付開始日ごとの生産量と生産性.html")

    def test_to_csv(self):
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = WholeProductivityPerFirstAnnotationStartedDate.create(df_task)

        WholeProductivityPerFirstAnnotationStartedDate.to_csv(df, self.output_dir / "教師付開始日ごとの生産量と生産性.csv")

    def test_merge(self):
        df1 = pandas.read_csv(str(data_path / "教師付開始日毎の生産量と生産性.csv"))
        df2 = pandas.read_csv(str(data_path / "教師付開始日毎の生産量と生産性2.csv"))
        sum_df = WholeProductivityPerFirstAnnotationStartedDate.merge(df1, df2)
        WholeProductivityPerFirstAnnotationStartedDate.to_csv(sum_df, self.output_dir / "merge-教師付開始日毎の生産量と生産性.csv")


class TestWholeProductivityPerCompletedDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))

        cls.df = WholeProductivityPerCompletedDate.create(df_task, df_labor)

    def test_create2(self):
        # 完了タスクが１つもない状態で試す
        df_task = pandas.read_csv(str(data_path / "only-working-task.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df = WholeProductivityPerCompletedDate.create(df_task, df_labor)

    def test_create3(self):
        # 完了タスクが１つもない状態で試す
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_labor = pandas.DataFrame()
        df = WholeProductivityPerCompletedDate.create(df_task, df_labor)

    def test_to_csv(self):
        WholeProductivityPerCompletedDate.to_csv(self.df, self.output_dir / "日ごとの生産量と生産性.csv")

    def test_plot(self):
        WholeProductivityPerCompletedDate.plot(self.df, self.output_dir / "折れ線-横軸_日-全体.html")

    def test_plot_cumulatively(self):
        WholeProductivityPerCompletedDate.plot_cumulatively(self.df, self.output_dir / "累積折れ線-横軸_日-全体.html")

    def test_merge(self):
        df1 = pandas.read_csv(str(data_path / "productivity-per-date.csv"))
        df2 = pandas.read_csv(str(data_path / "productivity-per-date2.csv"))
        sum_df = WholeProductivityPerCompletedDate.merge(df1, df2)
        WholeProductivityPerCompletedDate.to_csv(sum_df, self.output_dir / "merge-productivity-per-date.csv")


class TestAnnotatorProductivityPerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_task = pandas.read_csv("out/task4.csv")
        cls.obj = AnnotatorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "教師付開始日ごとの教師付者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "折れ線-横軸_教師付開始日-縦軸_入力データあたりの指標-教師付者用.html")


class TestInspectorProductivityPerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df_task = pandas.read_csv("out/task4.csv")

        cls.obj = InspectorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv( self.output_dir / "検査開始日ごとの検査者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(
            self.output_dir / "折れ線-横軸_検査開始日-縦軸_アノテーションあたりの指標-検査者用.html"
        )

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(
            self.output_dir / "折れ線-横軸_検査開始日-縦軸_入力データあたりの指標-検査者用.html"
        )


class TestAcceptorProductivityPerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))

        cls.obj = AcceptorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv( self.output_dir / "受入開始日ごとの受入者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(
            self.output_dir / "折れ線-横軸_受入開始日-縦軸_アノテーションあたりの指標-受入者用.html"
        )

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(
            self.output_dir / "折れ線-横軸_受入開始日-縦軸_入力データあたりの指標-受入者用.html"
        )
