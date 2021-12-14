import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

out_dir = Path("./tests/out/statistics")
data_dir = Path("./tests/data/statistics")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_list_annotation_count_by_task(self):
        output_dir = str(out_dir / "list_annotation_count_by_task-out")
        main(
            [
                "statistics",
                "list_annotation_count",
                "--project_id",
                project_id,
                "--output_dir",
                output_dir,
                "--group_by",
                "task_id",
            ]
        )

    def test_list_annotation_count_by_input_data(self):
        output_dir = str(out_dir / "list_annotation_count_by_input_data-out")
        main(
            [
                "statistics",
                "list_annotation_count",
                "--project_id",
                project_id,
                "--output_dir",
                output_dir,
                "--group_by",
                "task_id",
            ]
        )

    def test_list_by_date_user(self):
        main(
            [
                "statistics",
                "list_by_date_user",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_by_date_user-out.csv"),
            ]
        )

    def test_list_cumulative_labor_time(self):
        main(
            [
                "statistics",
                "list_cumulative_labor_time",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_cumulative_labor_time-out.csv"),
            ]
        )

    def test_list_labor_time_per_user(self):
        main(
            [
                "statistics",
                "list_labor_time_per_user",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_labor_time_per_user-out.csv"),
            ]
        )

    def test_list_task_progress(self):
        main(
            [
                "statistics",
                "list_task_progress",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "task-progress-out.csv"),
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

    def test_summarize_task_count_by_task_id(self):
        main(
            [
                "statistics",
                "summarize_task_count_by_task_id",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "summarize_task_count_by_task_id.csv"),
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


# class TestListSubmittedTaskCountMain:
#     main_obj = None
#
#     @classmethod
#     def setup_class(cls):
#         cls.main_obj = ListSubmittedTaskCountMain(service)
#
#     def test_create_labor_df(self):
#         df = self.main_obj.create_labor_df(project_id)
#         df.to_csv("labor_df.csv")
#
#     def test_create_account_statistics_df(self):
#         df = self.main_obj.create_account_statistics_df(project_id)
#         df.to_csv("account_statistics.csv")
#
#     def test_create_user_df(self):
#         df = self.main_obj.create_user_df(project_id)
#         df.to_csv("user.csv")
