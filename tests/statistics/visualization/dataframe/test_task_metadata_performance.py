from pathlib import Path

import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.task_metadata_performance import (
    EMPTY_METADATA_VALUE,
    TaskMetadataPerformance,
)
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

data_dir = Path("./tests/data/statistics")

custom_production_volume_list = [
    ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
    ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
]


class TestTaskMetadataPerformance:
    def test__from_df_wrapper(self):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task.df["metadata"] = task.df["task_id"].map(
            {
                "task1": {"category": "A"},
                "task2": {"category": "B"},
            }
        )
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)

        actual = TaskMetadataPerformance.from_df_wrapper(
            task=task,
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            metadata_key="category",
            real_monitored_worktime_hour_per_real_actual_worktime_hour=2,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )

        df = actual.df.set_index(("category", ""))

        assert df.loc["A", ("monitored_worktime_hour", "annotation")] == pytest.approx(2)
        assert df.loc["A", ("actual_worktime_hour", "annotation")] == pytest.approx(1)
        assert df.loc["A", ("task_count", "annotation")] == pytest.approx(1)
        assert df.loc["A", ("monitored_worktime_hour/task_count", "annotation")] == pytest.approx(2)
        assert df.loc["A", ("actual_worktime_hour/task_count", "annotation")] == pytest.approx(1)
        assert df.loc["A", ("pointed_out_inspection_comment_count", "annotation")] == pytest.approx(5)
        assert df.loc["A", ("pointed_out_inspection_comment_count/annotation_count", "annotation")] == pytest.approx(0.05)
        assert df.loc["A", ("rejected_count/task_count", "annotation")] == pytest.approx(1)

        assert df.loc["B", ("monitored_worktime_hour", "acceptance")] == pytest.approx(0.1)
        assert df.loc["B", ("actual_worktime_hour", "acceptance")] == pytest.approx(0.05)
        assert ("real_monitored_worktime_hour/real_actual_worktime_hour", "sum") not in df.columns

    def test__from_df_wrapper__metadataが存在しない場合は空欄にする(self):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)

        actual = TaskMetadataPerformance.from_df_wrapper(
            task=task,
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            metadata_key="category",
            real_monitored_worktime_hour_per_real_actual_worktime_hour=2,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )

        assert list(actual.df[("category", "")]) == [EMPTY_METADATA_VALUE]

    def test__from_df_wrapper__metadata_keyが既存列名と重複している(self):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task.df["metadata"] = task.df["task_id"].map({"task1": {"phase": "A"}, "task2": {"phase": "B"}})
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)

        actual = TaskMetadataPerformance.from_df_wrapper(
            task=task,
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            metadata_key="phase",
            real_monitored_worktime_hour_per_real_actual_worktime_hour=2,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )

        df = actual.df.set_index(("phase", ""))
        assert df.loc["A", ("monitored_worktime_hour", "annotation")] == pytest.approx(2)

    def test__from_df_wrapper__acceptance_reachedでは受入フェーズの値を0にする(self):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task.df["metadata"] = task.df["task_id"].map(
            {
                "task1": {"category": "A"},
                "task2": {"category": "B"},
            }
        )
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)

        actual = TaskMetadataPerformance.from_df_wrapper(
            task=task,
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            metadata_key="category",
            real_monitored_worktime_hour_per_real_actual_worktime_hour=2,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_REACHED,
        )

        df = actual.df.set_index(("category", ""))
        assert df.loc["B", ("monitored_worktime_hour", "acceptance")] == pytest.approx(0)
        assert df.loc["B", ("actual_worktime_hour", "acceptance")] == pytest.approx(0)
        assert df.loc["B", ("task_count", "acceptance")] == pytest.approx(0)
        assert df.loc["B", ("annotation_count", "acceptance")] == pytest.approx(0)

    def test__to_csv(self, tmp_path: Path):
        task = Task.from_csv(data_dir / "task.csv", custom_production_volume_list=custom_production_volume_list)
        task.df["project_id"] = "prj1"
        task.df["metadata"] = task.df["task_id"].map({"task1": {"category": "A"}, "task2": {"category": "B"}})
        task_worktime_by_phase_user = TaskWorktimeByPhaseUser.from_csv(data_dir / "task-worktime-by-user-phase.csv", custom_production_volume_list=custom_production_volume_list)
        actual = TaskMetadataPerformance.from_df_wrapper(
            task=task,
            task_worktime_by_phase_user=task_worktime_by_phase_user,
            metadata_key="category",
            real_monitored_worktime_hour_per_real_actual_worktime_hour=2,
            task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED,
        )

        output_file = tmp_path / "categoryごとの生産性と品質.csv"
        actual.to_csv(output_file)

        df = pandas.read_csv(output_file, header=[0, 1])
        assert ("category", "Unnamed: 0_level_1") in df.columns
        assert ("actual_worktime_hour/task_count", "annotation") in df.columns
