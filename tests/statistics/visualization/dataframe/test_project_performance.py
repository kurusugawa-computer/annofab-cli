from pathlib import Path

import numpy

from annofabcli.statistics.visualization.dataframe.project_performance import (
    ProjectPerformance,
    ProjectWorktimePerMonth,
)
from annofabcli.statistics.visualization.model import TaskCompletionCriteria, WorktimeColumn
from annofabcli.statistics.visualization.project_dir import ProjectDir

output_dir = Path("./tests/out/statistics/visualization/dataframe/project_performance")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestProjectPerformance:
    def test__from_project_dirs__and__to_csv(self):
        actual = ProjectPerformance.from_project_dirs([ProjectDir(data_dir / "visualization-dir1", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)])
        df = actual.df
        assert len(df) == 1
        row = df.iloc[0]

        # メインの項目だけチェックする
        assert row[("dirname", "")] == "visualization-dir1"
        assert row[("project_title", "")] == "test-project"
        assert row[("input_data_type", "")] == "image"
        assert row[("first_working_date", "")] == "2023-10-25"

        actual.to_csv(output_dir / "test__from_project_dirs__and__to_csv.csv")

    def test__from_project_dirs__空ディレクトから生成する(self):
        actual = ProjectPerformance.from_project_dirs([ProjectDir(data_dir / "empty", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)])
        df = actual.df
        assert len(df) == 1
        row = df.iloc[0]
        # メインの項目をアサートする
        assert row[("dirname", "")] == "empty"
        assert numpy.isnan(row[("project_title", "")])
        assert numpy.isnan(row[("first_working_date", "")])
        assert row[("actual_worktime_hour", "sum")] == 0

        actual.to_csv(output_dir / "test__from_project_dirs__空ディレクトから生成する.csv")


class TestProjectWorktimePerMonth:
    def test__from_project_dirs__and_to_csv(self):
        actual_worktime = ProjectWorktimePerMonth.from_project_dirs(
            [ProjectDir(data_dir / "visualization-dir1", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)],
            worktime_column=WorktimeColumn.ACTUAL_WORKTIME_HOUR,
        )
        df = actual_worktime.df
        assert len(df) == 1
        row = df.iloc[0]
        assert row["dirname"] == "visualization-dir1"
        assert row["2022-01"] == 3
        assert row["2022-02"] == 7

        actual_worktime.to_csv(output_dir / "test__from_project_dirs__and_to_csv.csv")

    def test__from_project_dirs__空ディレクトリから生成(self):
        actual_worktime = ProjectWorktimePerMonth.from_project_dirs([ProjectDir(data_dir / "empty", TaskCompletionCriteria.ACCEPTANCE_COMPLETED)], worktime_column=WorktimeColumn.ACTUAL_WORKTIME_HOUR)
        df = actual_worktime.df
        assert len(df) == 1
        row = df.iloc[0]
        assert row["dirname"] == "empty"

        actual_worktime.to_csv(output_dir / "test__from_project_dirs__空ディレクトリから生成.csv")
