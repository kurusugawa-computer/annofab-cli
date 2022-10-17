import json
from pathlib import Path

import pandas

from annofabcli.stat_visualization.write_performance_rating_csv import (
    CollectingPerformanceInfo,
    PerformanceUnit,
    ProductivityType,
    ThresholdInfo,
)
from annofabcli.statistics.list_worktime import WorktimeFromTaskHistoryEvent, get_df_worktime
from annofabcli.statistics.summarize_task_count_by_task_id_group import create_task_count_summary_df, get_task_id_prefix
from annofabcli.statistics.table import Table
from annofabcli.statistics.visualization.model import WorktimeColumn
from annofabcli.task_history_event.list_worktime import SimpleTaskHistoryEvent

out_path = Path("./tests/out/statistics")
data_path = Path("./tests/data/statistics")
out_path.mkdir(exist_ok=True, parents=True)

project_id = "12345678-abcd-1234-abcd-1234abcd5678"


class TestTable:
    def test_get_task_history_df(self):
        task_history_df = pandas.read_csv(str(data_path / "task-history-df.csv"))
        task_df = pandas.DataFrame(
            {
                "task_id": ["task1", "task2"],
                "annotation_count": [100, 200],
                "input_data_count": [2, 4],
                "inspection_comment_count": [5, 6],
                "number_of_rejections_by_inspection": [1, 2],
                "number_of_rejections_by_acceptance": [3, 4],
            }
        )
        df = Table.create_annotation_count_ratio_df(task_history_df, task_df)
        df.to_csv(out_path / "annotation-count-ratio.csv")

    def test_create_annotation_count_ratio_df(self):
        df_task_history = pandas.read_csv(str(data_path / "task-history-df.csv"))
        df_task = pandas.read_csv(str(data_path / "task.csv"))
        df = Table.create_annotation_count_ratio_df(task_df=df_task, task_history_df=df_task_history)
        df.to_csv(out_path / "annotation-count-ratio-df.csv")


class TestSummarizeTaskCountByTaskId:
    # task_list = [
    #     {"task_id": "A_A_01", "status": "complete", "phase":"acceptance", "phase_stage":1},
    #     {"task_id": "A_A_02", "status": "not_started", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "A_B_02", "status": "on_hold", "phase":"annotation", "phase_stage":1},
    #     {"task_id": "abc", "status": "break", "phase":"acceptance", "phase_stage":1},
    # ]

    def test_get_task_id_prefix(self):
        assert get_task_id_prefix("A_A_01", delimiter="_") == "A_A"
        assert get_task_id_prefix("abc", delimiter="_") == "unknown"

    def test_create_task_count_summary_df(self):
        with (data_path / "task.json").open(encoding="utf-8") as f:
            task_list = json.load(f)
        df = create_task_count_summary_df(task_list, task_id_delimiter="_", task_id_groups=None)
        assert len(df) == 1
        df.iloc[0]["task_id_group"] == "sample"


class TestListWorktime:
    def test_get_df_worktime(self):
        event_list = [
            WorktimeFromTaskHistoryEvent(
                project_id="prj1",
                task_id="task1",
                phase="annotation",
                phase_stage=1,
                account_id="alice",
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
                account_id="bob",
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
            {"account_id": "alice", "user_id": "alice", "username": "Alice", "biography": "U.S."},
            {"account_id": "bob", "user_id": "bob", "username": "Bob", "biography": "Japan"},
        ]
        df = get_df_worktime(event_list, member_list)


class TestCollectingPerformanceInfo:
    def test_get_threshold_info(self):
        obj = CollectingPerformanceInfo(
            WorktimeColumn.ACTUAL_WORKTIME_HOUR,
            PerformanceUnit.ANNOTATION_COUNT,
            threshold_info=ThresholdInfo(threshold_worktime=10, threshold_task_count=20),
            threshold_infos_per_project={
                ("dir1", ProductivityType.ANNOTATION): ThresholdInfo(None, None),
                ("dir2", ProductivityType.ANNOTATION): ThresholdInfo(11, None),
                ("dir3", ProductivityType.ANNOTATION): ThresholdInfo(None, 21),
                ("dir4", ProductivityType.ANNOTATION): ThresholdInfo(12, 22),
            },
        )

        assert obj.get_threshold_info("not-exists", ProductivityType.ANNOTATION) == ThresholdInfo(10, 20)
        assert obj.get_threshold_info("dir1", ProductivityType.ANNOTATION) == ThresholdInfo(10, 20)
        assert obj.get_threshold_info("dir2", ProductivityType.ANNOTATION) == ThresholdInfo(11, 20)
        assert obj.get_threshold_info("dir3", ProductivityType.ANNOTATION) == ThresholdInfo(10, 21)
        assert obj.get_threshold_info("dir4", ProductivityType.ANNOTATION) == ThresholdInfo(12, 22)
