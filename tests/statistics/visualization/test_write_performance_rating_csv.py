from pathlib import Path

import pandas
from pytest import approx

from annofabcli.stat_visualization.write_performance_rating_csv import (
    CollectingPerformanceInfo,
    ProductivityIndicator,
    ProductivityType,
    QualityIndicator,
    TaskPhase,
    ThresholdInfo,
    create_productivity_indicator_by_directory,
    create_quality_indicator_by_directory,
    create_threshold_infos_per_project,
)
from annofabcli.statistics.visualization.project_dir import ProjectDir, TaskCompletionCriteria

data_dir = Path("tests/data/stat_visualization")


def test__create_threshold_infos_per_project():
    actual = create_threshold_infos_per_project('{"dirname": {"annotation": {"threshold_worktime": 11, "threshold_task_count": 21}}}')
    assert actual == {("dirname", ProductivityType.ANNOTATION): ThresholdInfo(11, 21)}


def test__create_productivity_indicator_by_directory():
    actual = create_productivity_indicator_by_directory('{"dirname": "monitored_worktime_hour/annotation_count"}')
    assert actual == {"dirname": ProductivityIndicator("monitored_worktime_hour/annotation_count")}


def test__create_quality_indicator_by_directory():
    actual = create_quality_indicator_by_directory('{"dirname": "rejected_count/task_count"}')
    assert actual == {"dirname": QualityIndicator("rejected_count/task_count")}


df_user = pandas.DataFrame(
    {
        ("user_id", ""): ["QU", "KX", "BH", "NZ"],
        ("username", ""): ["QU", "KX", "BH", "NZ"],
        ("biography", ""): ["category-KK", "category-KT", "category-KT", "category-KT"],
    }
)
project_dir = ProjectDir(data_dir / "visualization-dir", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)

user_performance = project_dir.read_user_performance()


class TestCollectingPerformanceInfo:
    def test__get_threshold_info(self):
        obj = CollectingPerformanceInfo(
            threshold_info=ThresholdInfo(threshold_worktime=10, threshold_task_count=20),
            threshold_infos_by_directory={
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

    def test__join_annotation_productivity(self):
        obj = CollectingPerformanceInfo()
        df_actual = obj.join_annotation_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual.columns[3] == ("project1", "actual_worktime_hour/annotation_count__annotation")
        assert df_actual.iloc[0][("project1", "actual_worktime_hour/annotation_count__annotation")] == approx(0.00070, rel=1e-2)

        obj2 = CollectingPerformanceInfo(productivity_indicator=ProductivityIndicator("monitored_worktime_hour/annotation_count"))
        df_actual2 = obj2.join_annotation_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual2.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__annotation")

        # productivity_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator("actual_worktime_hour/annotation_count"),
            productivity_indicator_by_directory={"project1": ProductivityIndicator("monitored_worktime_hour/annotation_count")},
        )
        df_actual3 = obj3.join_annotation_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual3.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__annotation")

    def test__join_inspection_acceptance_productivity(self):
        obj = CollectingPerformanceInfo()
        df_actual = obj.join_inspection_acceptance_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual.columns[3] == ("project1", "actual_worktime_hour/annotation_count__acceptance")
        assert df_actual.iloc[1][("project1", "actual_worktime_hour/annotation_count__acceptance")] == approx(0.000145, rel=1e-2)

        obj2 = CollectingPerformanceInfo(productivity_indicator=ProductivityIndicator("monitored_worktime_hour/annotation_count"))
        df_actual2 = obj2.join_inspection_acceptance_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual2.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__acceptance")

        # productivity_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator("actual_worktime_hour/annotation_count"),
            productivity_indicator_by_directory={"project1": ProductivityIndicator("monitored_worktime_hour/annotation_count")},
        )
        df_actual3 = obj3.join_inspection_acceptance_productivity(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual3.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__acceptance")

    def test__join_annotation_quality(self):
        obj = CollectingPerformanceInfo()
        df_actual = obj.join_annotation_quality(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual.columns[3] == ("project1", "pointed_out_inspection_comment_count/annotation_count__annotation")
        assert df_actual.iloc[0][("project1", "pointed_out_inspection_comment_count/annotation_count__annotation")] == approx(0.000854, rel=1e-2)

        obj2 = CollectingPerformanceInfo(quality_indicator=QualityIndicator("rejected_count/task_count"))
        df_actual2 = obj2.join_annotation_quality(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual2.columns[3] == ("project1", "rejected_count/task_count__annotation")

        # quality_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            quality_indicator=QualityIndicator("pointed_out_inspection_comment_count/input_data_count"),
            quality_indicator_by_directory={"project1": QualityIndicator("rejected_count/task_count")},
        )
        df_actual3 = obj3.join_annotation_quality(df=df_user, df_performance=user_performance.df, project_title="project1")
        assert df_actual3.columns[3] == ("project1", "rejected_count/task_count__annotation")

    def test__filter_df_with_threshold(self):
        # threshold_worktime で絞り込み
        obj = CollectingPerformanceInfo(threshold_info=ThresholdInfo(threshold_worktime=6, threshold_task_count=None))
        df_actual = obj.filter_df_with_threshold(df=user_performance.df, phase=TaskPhase.ANNOTATION, project_title="project1")
        assert list(df_actual["user_id"]) == ["KX"]

        # threshold_task_count で絞り込み
        obj = CollectingPerformanceInfo(threshold_info=ThresholdInfo(threshold_worktime=None, threshold_task_count=40))
        df_actual = obj.filter_df_with_threshold(df=user_performance.df, phase=TaskPhase.ANNOTATION, project_title="project1")
        assert list(df_actual["user_id"]) == ["BH"]

        # threshold_task_count で絞り込み
        obj = CollectingPerformanceInfo(
            threshold_info=ThresholdInfo(threshold_worktime=100, threshold_task_count=100),
            threshold_infos_by_directory={("project1", ProductivityType.ANNOTATION): ThresholdInfo(threshold_worktime=6, threshold_task_count=0)},
        )
        df_actual = obj.filter_df_with_threshold(df=user_performance.df, phase=TaskPhase.ANNOTATION, project_title="project1")
        assert list(df_actual["user_id"]) == ["KX"]
