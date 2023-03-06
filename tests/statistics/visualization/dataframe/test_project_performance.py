from pathlib import Path

import numpy

from annofabcli.statistics.visualization.dataframe.project_performance import (
    ProjectPerformance,
    ProjectWorktimePerMonth,
)
from annofabcli.statistics.visualization.model import WorktimeColumn
from annofabcli.statistics.visualization.project_dir import ProjectDir

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestProjectPerformance:
    obj: ProjectPerformance

    @classmethod
    def setup_class(cls):
        cls.obj = ProjectPerformance.from_project_dirs([ProjectDir(data_dir / "visualization-dir1")])

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "プロジェクごとの生産性と品質.csv")

    def test_instance(self):
        df = self.obj.df
        assert len(df) == 1
        row = df.iloc[0]
        # メインの項目をアサートする
        assert row[("dirname", "")] == "visualization-dir1"
        assert row[("project_title", "")] == "test-project"
        assert row[("start_date", "")] == "2022-01-01"
        assert row[("actual_worktime_hour", "sum")] == 4503

    def test_from_project_dirs_with_empty(self):
        obj = ProjectPerformance.from_project_dirs([ProjectDir(data_dir / "empty")])
        df = obj.df
        assert len(df) == 1
        row = df.iloc[0]
        # メインの項目をアサートする
        assert row[("dirname", "")] == "empty"
        assert numpy.isnan(row[("project_title", "")])
        assert numpy.isnan(row[("start_date", "")])
        assert row[("actual_worktime_hour", "sum")] == 0


class TestProjectWorktimePerMonth:
    def test_from_project_dirs(self):
        actual_worktime = ProjectWorktimePerMonth.from_project_dirs(
            [ProjectDir(data_dir / "visualization-dir1")], worktime_column=WorktimeColumn.ACTUAL_WORKTIME_HOUR
        )
        df = actual_worktime.df
        assert len(df) == 1
        row = df.iloc[0]
        assert row["dirname"] == "visualization-dir1"
        assert row["2022-01"] == 3
        assert row["2022-02"] == 7

    def test_from_project_dirs_empty_dir(self):
        actual_worktime = ProjectWorktimePerMonth.from_project_dirs(
            [ProjectDir(data_dir / "empty")], worktime_column=WorktimeColumn.ACTUAL_WORKTIME_HOUR
        )
        df = actual_worktime.df
        assert len(df) == 1
        row = df.iloc[0]
        assert row["dirname"] == "empty"
