from pathlib import Path

import pandas
from pytest import approx

from annofabcli.stat_visualization.write_performance_rating_csv import (
    CollectingPerformanceInfo,
    ProductivityIndicator,
    ProductivityType,
    QualityIndicator,
    ThresholdInfo,
    create_productivity_indicator_by_directory,
    create_quality_indicator_by_directory,
    create_threshold_infos_per_project,
)
from annofabcli.statistics.visualization.project_dir import ProjectDir

data_dir = Path("tests/data/stat_visualization")


def test__create_threshold_infos_per_project():
    actual = create_threshold_infos_per_project(
        '{"dirname": {"annotation": {"threshold_worktime": 11, "threshold_task_count": 21}}}'
    )
    assert actual == {("dirname", ProductivityType.ANNOTATION): ThresholdInfo(11, 21)}


def test__create_productivity_indicator_by_directory():
    actual = create_productivity_indicator_by_directory('{"dirname": "monitored_worktime_hour/annotation_count"}')
    assert actual == {"dirname": ProductivityIndicator.MONITORED_WORKTIME_HOUR_PER_ANNOTATION_COUNT}


def test__create_quality_indicator_by_directory():
    actual = create_quality_indicator_by_directory('{"dirname": "rejected_count/task_count"}')
    assert actual == {"dirname": QualityIndicator.REJECTED_COUNT_PER_TASK_COUNT}


df_user = pandas.DataFrame(
    {
        ("user_id", ""): ["QU", "KX", "BH", "NZ"],
        ("username", ""): ["QU", "KX", "BH", "NZ"],
        ("biography", ""): ["category-KK", "category-KT", "category-KT", "category-KT"],
    }
)

project_dir = ProjectDir(data_dir / "visualization-dir")

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
        df_actual = obj.join_annotation_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual.columns[3] == ("project1", "actual_worktime_hour/annotation_count__annotation")
        assert df_actual.iloc[0][("project1", "actual_worktime_hour/annotation_count__annotation")] == approx(
            0.00070, rel=1e-2
        )

        obj2 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator.MONITORED_WORKTIME_HOUR_PER_ANNOTATION_COUNT
        )
        df_actual2 = obj2.join_annotation_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual2.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__annotation")

        # productivity_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator.ACTUAL_WORKTIME_HOUR_PER_ANNOTATION_COUNT,
            productivity_indicator_by_directory={
                "project1": ProductivityIndicator.MONITORED_WORKTIME_HOUR_PER_ANNOTATION_COUNT
            },
        )
        df_actual3 = obj3.join_annotation_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual3.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__annotation")

    def test__join_inspection_acceptance_productivity(self):
        obj = CollectingPerformanceInfo()
        df_actual = obj.join_inspection_acceptance_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual.columns[3] == ("project1", "actual_worktime_hour/annotation_count__acceptance")
        assert df_actual.iloc[1][("project1", "actual_worktime_hour/annotation_count__acceptance")] == approx(
            0.000145, rel=1e-2
        )

        obj2 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator.MONITORED_WORKTIME_HOUR_PER_ANNOTATION_COUNT
        )
        df_actual2 = obj2.join_inspection_acceptance_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual2.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__acceptance")

        # productivity_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            productivity_indicator=ProductivityIndicator.ACTUAL_WORKTIME_HOUR_PER_ANNOTATION_COUNT,
            productivity_indicator_by_directory={
                "project1": ProductivityIndicator.MONITORED_WORKTIME_HOUR_PER_ANNOTATION_COUNT
            },
        )
        df_actual3 = obj3.join_inspection_acceptance_productivity(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual3.columns[3] == ("project1", "monitored_worktime_hour/annotation_count__acceptance")

    def test__join_annotation_quality(self):
        obj = CollectingPerformanceInfo()
        df_actual = obj.join_annotation_quality(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        print(df_actual)
        assert df_actual.columns[3] == ("project1", "pointed_out_inspection_comment_count/annotation_count__annotation")
        assert df_actual.iloc[0][
            ("project1", "pointed_out_inspection_comment_count/annotation_count__annotation")
        ] == approx(0.000854, rel=1e-2)

        obj2 = CollectingPerformanceInfo(quality_indicator=QualityIndicator.REJECTED_COUNT_PER_TASK_COUNT)
        df_actual2 = obj2.join_annotation_quality(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual2.columns[3] == ("project1", "rejected_count/task_count__annotation")

        # quality_indicator_by_directoryが優先されることを確認
        obj3 = CollectingPerformanceInfo(
            quality_indicator=QualityIndicator.POINTED_OUT_INSPECTION_COMMENT_COUNT_PER_INPUT_DATA_COUNT,
            quality_indicator_by_directory={"project1": QualityIndicator.REJECTED_COUNT_PER_TASK_COUNT},
        )
        df_actual3 = obj3.join_annotation_quality(
            df=df_user, df_performance=user_performance.df, project_title="project1"
        )
        assert df_actual3.columns[3] == ("project1", "rejected_count/task_count__annotation")
