from annofabcli.stat_visualization.write_performance_rating_csv import (
    CollectingPerformanceInfo,
    PerformanceUnit,
    ProductivityType,
    ThresholdInfo,
)
from annofabcli.statistics.visualization.model import WorktimeColumn


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
