import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/statistics")
data_dir = Path("./tests/data/statistics")
out_dir.mkdir(exist_ok=True, parents=True)


inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()

video_project_id = annofab_config["video_project_id"]


class TestCommandLine:
    def test_list_annotation_attribute(self):
        main(
            [
                "statistics",
                "list_annotation_attribute",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "test_list_annotation_attribute-out.csv"),
                "--format",
                "csv",
            ]
        )

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

    def test_list_annotation_duration(self):
        main(
            [
                "statistics",
                "list_annotation_duration",
                "--project_id",
                video_project_id,
                "--output",
                str(out_dir / "test_list_annotation_duration-out.csv"),
                "--format",
                "csv",
            ]
        )

    def test_list_video_duration(self):
        main(
            [
                "statistics",
                "list_video_duration",
                "--project_id",
                video_project_id,
                "--output",
                str(out_dir / "test_list_video_duration-out.csv"),
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

    def test__visualize_video_duration(self) -> None:
        main(["statistics", "visualize_video_duration", "--project_id", video_project_id, "--output", str(out_dir / "visualize_video_duration.html")])
