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
from annofabcli.statistics.visualization.model import WorktimeColumn


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


class TestCollectingPerformanceInfo:
    def test_get_threshold_info(self):
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
