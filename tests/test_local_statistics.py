import collections
import json
from pathlib import Path

import pandas
from annofabapi.models import TaskStatus

from annofabcli.statistics.csv import Csv
from annofabcli.statistics.list_annotation_count import (
    GroupBy,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
)
from annofabcli.statistics.list_worktime import WorktimeFromTaskHistoryEvent, get_df_worktime
from annofabcli.statistics.summarize_task_count import SimpleTaskStatus, get_step_for_current_phase
from annofabcli.statistics.summarize_task_count_by_task_id import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)
from annofabcli.statistics.visualization.dataframe.user_performance import (
    ProjectPerformance,
    UserPerformance,
    WholePerformance,
)
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualize_annotation_count import plot_attribute_histogram, plot_label_histogram
from annofabcli.task_history_event.list_worktime import SimpleTaskHistoryEvent

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

        cls.obj = InspectorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "検査開始日ごとの検査者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "折れ線-横軸_検査開始日-縦軸_アノテーションあたりの指標-検査者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "折れ線-横軸_検査開始日-縦軸_入力データあたりの指標-検査者用.html")


class TestAcceptorProductivityPerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))

        cls.obj = AcceptorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "受入開始日ごとの受入者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "折れ線-横軸_受入開始日-縦軸_アノテーションあたりの指標-受入者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "折れ線-横軸_受入開始日-縦軸_入力データあたりの指標-受入者用.html")


class TestAnnotatorProductivityPerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        cls.obj = AnnotatorProductivityPerDate.from_df_task(df_task)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "教師付開始日ごとの教師付者の生産性.csv")

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "折れ線-横軸_教師付開始日-縦軸_アノテーションあたりの指標-教師付者用.html")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "折れ線-横軸_教師付開始日-縦軸_入力データあたりの指標-教師付者用.html")


class TestAnnotatorCumulativeProductivity:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        cls.obj = AnnotatorCumulativeProductivity(df_task)

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "累積折れ線-横軸_アノテーション数-教師付者用")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "累積折れ線-横軸_入力データ数-教師付者用")

    def test_plot_task_metrics(self):
        self.obj.plot_task_metrics(self.output_dir / "累積折れ線-横軸_タスク数-教師付者用")


class TestInspectorCumulativeProductivity:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        cls.obj = InspectorCumulativeProductivity(df_task)

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "累積折れ線-横軸_アノテーション数-検査者用")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "累積折れ線-横軸_入力データ数-検査者用")


class TestAcceptorCumulativeProductivity:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df_task = pandas.read_csv(str(data_path / "task.csv"))
        cls.obj = AcceptorCumulativeProductivity(df_task)

    def test_plot_annotation_metrics(self):
        self.obj.plot_annotation_metrics(self.output_dir / "累積折れ線-横軸_アノテーション数-受入者用")

    def test_plot_input_data_metrics(self):
        self.obj.plot_input_data_metrics(self.output_dir / "累積折れ線-横軸_入力データ数-受入者用")


class TestListWorktime:
    def test_get_df_worktime(self):
        event_list = [
            WorktimeFromTaskHistoryEvent(
                project_id="prj1",
                task_id="task1",
                phase="annotation",
                phase_stage=1,
                account_id="unknown",
                user_id="alice",
                username="Alice",
                worktime_hour=3.0,
                start_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-01T23:00:00.000+09:00", status="working"
                ),
                end_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-02T02:00:00.000+09:00", status="on_holding"
                ),
            ),
            WorktimeFromTaskHistoryEvent(
                project_id="prj1",
                task_id="task2",
                phase="acceptance",
                phase_stage=1,
                account_id="unknown",
                user_id="bob",
                username="Bob",
                worktime_hour=1.0,
                start_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-03T22:00:00.000+09:00", status="working"
                ),
                end_event=SimpleTaskHistoryEvent(
                    task_history_id="unknown", created_datetime="2019-01-03T23:00:00.000+09:00", status="on_holding"
                ),
            ),
        ]

        member_list = [
            {"user_id": "alice", "username": "Alice", "biography": "U.S."},
            {"user_id": "bob", "username": "Bob", "biography": "Japan"},
        ]
        df = get_df_worktime(event_list, member_list)


class TestWorktimePerDate:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)

        df = pandas.read_csv(str(data_path / "ユーザ_日付list-作業時間.csv"))
        cls.obj = WorktimePerDate(df)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "ユーザ_日付list-作業時間.csv")

    def test_plot_cumulatively(self):
        self.obj.plot_cumulatively(self.output_dir / "累積折れ線-横軸_日-縦軸_作業時間.html")


class TestUserPerformance:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)
        cls.obj = UserPerformance.from_csv(data_path / "productivity-per-user2.csv")

    def test_from_df(self):
        df_task_history = pandas.read_csv(str(data_path / "task-history-df.csv"))
        df_labor = pandas.read_csv(str(data_path / "labor-df.csv"))
        df_worktime_ratio = pandas.read_csv(str(data_path / "annotation-count-ratio-df.csv"))
        UserPerformance.from_df(df_task_history, df_labor, df_worktime_ratio)

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "メンバごとの生産性と品質.csv")

    def test_plot_quality(self):
        self.obj.plot_quality(self.output_dir / "散布図-教師付者の品質と作業量の関係.html")

    def test_plot_productivity_from_actual_worktime(self):
        self.obj.plot_productivity_from_actual_worktime(self.output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html")

    def test_plot_productivity_from_monitored_worktime(self):
        self.obj.plot_productivity_from_monitored_worktime(self.output_dir / "散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html")

    def test_plot_quality_and_productivity_from_actual_worktime(self):
        self.obj.plot_quality_and_productivity_from_actual_worktime(
            self.output_dir / "散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html"
        )

    def test_plot_quality_and_productivity_from_monitored_worktime(self):
        self.obj.plot_quality_and_productivity_from_monitored_worktime(
            self.output_dir / "散布図-アノテーションあたり作業時間と品質の関係-計測時間-教師付者用.html"
        )

    def test_get_summary(self):
        ser = self.obj.get_summary()
        assert int(ser[("task_count", "annotation")]) == 45481

    def test_merge(self):
        merged_obj = UserPerformance.merge(self.obj, self.obj)
        row = merged_obj.df[merged_obj.df["user_id"] == "KD"].iloc[0]
        assert row[("task_count", "annotation")] == 30


class TestWholePerformance:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)
        cls.obj = WholePerformance.from_csv(data_path / "全体の生産性と品質.csv")

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "全体の生産性と品質.csv")


class TestProjectPerformance:
    @classmethod
    def setup_class(cls):
        cls.output_dir = out_path / "visualization"
        cls.output_dir.mkdir(exist_ok=True, parents=True)
        tmp = WholePerformance.from_csv(data_path / "全体の生産性と品質.csv")
        cls.obj = ProjectPerformance.from_whole_performance_objs([tmp, tmp], ["foo", "bar"])

    def test_to_csv(self):
        self.obj.to_csv(self.output_dir / "プロジェクごとの生産性と品質.csv")


class TestListAnnotationCounterByInputData:
    def test_get_annotation_counter(self):
        annotation = {
            "task_id": "task1",
            "task_phase": "acceptance",
            "task_phase_stage": 1,
            "task_status": "complete",
            "input_data_id": "input1",
            "input_data_name": "input1",
            "details": [
                {
                    "label": "bird",
                    "attributes": {
                        "weight": 4,
                        "occluded": True,
                    },
                },
                {
                    "label": "bird",
                    "attributes": {
                        "weight": 3,
                        "occluded": True,
                    },
                },
                {"label": "climatic", "attributes": {"weather": "sunny"}},
            ],
        }

        counter = ListAnnotationCounterByInputData.get_annotation_counter(annotation)
        assert counter.input_data_id == "input1"
        assert counter.task_id == "task1"
        assert counter.labels_counter == collections.Counter({"bird": 2, "climatic": 1})
        assert counter.attributes_counter == collections.Counter(
            {
                ("bird", "weight", "4"): 1,
                ("bird", "weight", "3"): 1,
                ("bird", "occluded", "True"): 2,
                ("climatic", "weather", "sunny"): 1,
            }
        )

        counter2 = ListAnnotationCounterByInputData.get_annotation_counter(
            annotation, target_labels=["climatic"], target_attributes=[("bird", "occluded","True")]
        )
        assert counter2.labels_counter == collections.Counter({"climatic": 1})
        assert counter2.attributes_counter == collections.Counter(
            {
                ("bird", "occluded", "True"): 2,
            }
        )

    def test_get_annotation_counter_list(self):
        counter_list = ListAnnotationCounterByInputData.get_annotation_counter_list(
            data_path / "simple-annotations.zip"
        )
        assert len(counter_list) == 4

    def test_print_labels_count(self):
        counter_list = ListAnnotationCounterByInputData.get_annotation_counter_list(
            data_path / "simple-annotations.zip"
        )
        ListAnnotationCounterByInputData.print_labels_count(
            counter_list,
            output_file=out_path / "list_annotation_count/labels_count_by_input_data.csv",
            label_columns=["dog", "human"],
        )

    def test_print_attributes_count(self):
        counter_list = ListAnnotationCounterByInputData.get_annotation_counter_list(
            data_path / "simple-annotations.zip"
        )
        ListAnnotationCounterByInputData.print_attributes_count(
            counter_list,
            output_file=out_path / "list_annotation_count/attributes_count_by_input_data.csv",
            attribute_columns=[("Cat", "occluded", "True"), ("climatic", "temparature", "20")],
        )


class TestListAnnotationCounterByTask:
    def test_get_annotation_counter_list(self):
        counter_list = ListAnnotationCounterByTask.get_annotation_counter_list(data_path / "simple-annotations.zip")
        assert len(counter_list) == 2

    def test_print_labels_count(self):
        counter_list = ListAnnotationCounterByTask.get_annotation_counter_list(data_path / "simple-annotations.zip")
        ListAnnotationCounterByTask.print_labels_count(
            counter_list,
            output_file=out_path / "list_annotation_count/labels_count_by_task.csv",
            label_columns=["dog", "human"],
        )

    def test_print_attributes_count(self):
        counter_list = ListAnnotationCounterByTask.get_annotation_counter_list(data_path / "simple-annotations.zip")
        ListAnnotationCounterByTask.print_attributes_count(
            counter_list,
            output_file=out_path / "list_annotation_count/attributes_count_by_task.csv",
            attribute_columns=[("Cat", "occluded", "True"), ("climatic", "temparature", "20")],
        )


class TestVisualizeAnnotationCount:
    def test_plot_label_histogram(self):
        counter_list = ListAnnotationCounterByInputData.get_annotation_counter_list(
            data_path / "simple-annotations.zip"
        )

        plot_label_histogram(
            counter_list,
            group_by=GroupBy.INPUT_DATA_ID,
            output_file=out_path / "visualize_annotation_count/labels_count_by_input_data.html",
        )

    def test_plot_attribute_histogram(self):
        counter_list = ListAnnotationCounterByTask.get_annotation_counter_list(data_path / "simple-annotations.zip")

        plot_attribute_histogram(
            counter_list,
            group_by=GroupBy.TASK_ID,
            output_file=out_path / "visualize_annotation_count/attributes_count_by_task.html",
        )
