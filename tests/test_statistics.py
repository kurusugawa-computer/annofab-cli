import configparser
import os
from pathlib import Path

import annofabapi
import pandas
import pytest
from annofabcli.__main__ import main
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
import pytest
# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/statistics")
data_dir = Path("./tests/data/statistics")
out_dir.mkdir(exist_ok=True, parents=True)


# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_list_annotation_count_by_task(self):
        main(
            [
                "statistics",
                "list_annotation_count",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_annotation_count_by_task-out.json"),
                "--group_by",
                "task_id",
                "--format",
                "pretty_json",
            ]
        )

    def test_list_annotation_count_by_input_data(self):
        main(
            [
                "statistics",
                "list_annotation_count",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_annotation_count_by_input_data-out.csv"),
                "--group_by",
                "input_data_id",
                "--type",
                "attribute",
                "--format",
                "csv",
            ]
        )

    def test_summarize_task_count(self):
        main(
            [
                "statistics",
                "summarize_task_count",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "summariz-task-count-out.csv"),
            ]
        )

    def test_summarize_task_count_by_task_id_group(self):
        main(
            [
                "statistics",
                "summarize_task_count_by_task_id_group",
                "--project_id",
                project_id,
                "--task_id_delimiter",
                "_",
                "--output",
                str(out_dir / "summarize_task_count_by_task_id_group.csv"),
            ]
        )

    def test_summarize_task_count_by_user(self):
        main(
            [
                "statistics",
                "summarize_task_count_by_user",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "summarize_task_count_by_user.csv"),
            ]
        )

    def test_visualize(self):
        main(
            [
                "statistics",
                "visualize",
                "--project_id",
                project_id,
                "--task_query",
                '{"status": "complete"}',
                "--output_dir",
                str(out_dir / "visualize-out"),
                "--minimal",
            ]
        )

    def test_list_worktime(self):
        main(
            [
                "statistics",
                "list_worktime",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list-worktime-out.csv"),
            ]
        )


class TestWorktimePerDate:
    def test_from_webapi(self):
        actual = WorktimePerDate.from_webapi(service, project_id)
        assert len(actual.df) > 0

    def test_from_webapi_with_labor(self):
        df_labor = pandas.read_csv(str(data_dir / "labor-df.csv"))
        actual = WorktimePerDate.from_webapi(service, project_id, df_labor=df_labor)
        assert len(actual.df) > 0
