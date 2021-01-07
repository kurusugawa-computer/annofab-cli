import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]

service = annofabapi.build_from_netrc()
user_id = service.api.login_user_id

out_path = Path("./tests/out")
data_path = Path("./tests/data")

organization_name = service.api.get_organization_of_project(project_id)[0]["organization_name"]


class TestInspectionComment:
    def test_list_inspection_comment(self):
        out_file = str(out_path / "inspection_comment.csv")
        main(["inspection_comment", "list", "--project_id", project_id, "--task_id", task_id, "--output", out_file])

    def test_list_unprocessed_inspection_comment(self):
        out_file = str(out_path / "inspection_comment.csv")
        main(
            [
                "inspection_comment",
                "list_unprocessed",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                out_file,
            ]
        )

    def test_list_inspection_comment_with_json(self):
        out_file = str(out_path / "inspection_comment.csv")
        main(
            [
                "inspection_comment",
                "list_with_json",
                "--project_id",
                project_id,
                "--exclude_reply",
                "--output",
                out_file,
            ]
        )


class TestInstruction:
    def test_upload_instruction(self):
        html_file = str(data_path / "instruction.html")
        main(["instruction", "upload", "--project_id", project_id, "--html", html_file])

    def test_copy_instruction(self):
        src_project_id = project_id
        dest_project_id = project_id
        main(["instruction", "copy", src_project_id, dest_project_id, "--yes"])


class TestJob:
    def test_list_job(self):
        out_file = str(out_path / "job.csv")
        main(
            [
                "job",
                "list",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
                "--format",
                "csv",
                "--output",
                out_file,
            ]
        )

    def test_list_last_job(self):
        out_file = str(out_path / "job.csv")
        main(
            [
                "job",
                "list_last",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
                "--format",
                "csv",
                "--output",
                out_file,
            ]
        )

    def test_wait_job(self):
        main(
            [
                "job",
                "wait",
                "--project_id",
                project_id,
                "--job_type",
                "delete-project",
            ]
        )


class TestLabor:
    def test_list_worktime_by_user_with_project_id(self):
        output_dir = str(out_path / "labor")
        main(
            [
                "labor",
                "list_worktime_by_user",
                "--project_id",
                project_id,
                "--user_id",
                service.api.login_user_id,
                "--start_date",
                "2019-09-01",
                "--end_date",
                "2019-09-01",
                "--add_availability",
                "--output_dir",
                str(output_dir),
            ]
        )

    def test_list_worktime_by_user_with_organization_name(self):
        output_dir = str(out_path / "labor")
        main(
            [
                "labor",
                "list_worktime_by_user",
                "--organization",
                organization_name,
                "--user_id",
                service.api.login_user_id,
                "--start_date",
                "2019-09-01",
                "--end_date",
                "2019-09-01",
                "--output_dir",
                str(output_dir),
            ]
        )


class TestProject:
    # def test_copy_project(self):
    #     # ジョブ登録されると、後続のテストが実行できなくなるので、存在しないプロジェクトIDを渡す
    #     main(['project', 'copy', '--project_id', 'not_exists_project_id', '--dest_title', 'copy-project'])

    def test_diff_project(self):
        main(["project", "diff", project_id, project_id])

    def test_download_project_task(self):
        out_file = str(out_path / "task.json")
        main(["project", "download", "task", "--project_id", project_id, "--output", out_file])

    def test_download_project_input_data(self):
        out_file = str(out_path / "input_data.json")
        main(["project", "download", "input_data", "--project_id", project_id, "--output", out_file])

    def test_download_project_inspection_comment(self):
        out_file = str(out_path / "inspection_comment.json")
        main(["project", "download", "inspection_comment", "--project_id", project_id, "--output", out_file])

    def test_download_project_task_history_event(self):
        out_file = str(out_path / "task_history_event.json")
        main(["project", "download", "task_history_event", "--project_id", project_id, "--output", out_file])

    def test_download_project_task_history(self):
        out_file = str(out_path / "task_history.json")
        main(["project", "download", "task_history", "--project_id", project_id, "--output", out_file])

    def test_download_project_simple_annotation(self):
        out_file = str(out_path / "simple_annotation.zip")
        main(["project", "download", "simple_annotation", "--project_id", project_id, "--output", out_file])

    def test_list_project(self):
        out_file = str(out_path / "project-list-from-organization.csv")
        main(
            [
                "project",
                "list",
                "--organization",
                organization_name,
                "--project_query",
                '{"status": "active"}',
                "--format",
                "csv",
                "--output",
                out_file,
            ]
        )

        out_file = str(out_path / "project-list-from-project-id.csv")
        main(
            [
                "project",
                "list",
                "--project_id",
                project_id,
                "--format",
                "csv",
                "--output",
                out_file,
            ]
        )

    def test_update_annotation_zip(self):
        main(["project", "update_annotation_zip", "--project_id", project_id])


class TestProjectMember:
    def test_put_project_member(self):
        csv_file = str(data_path / "project_members.csv")
        main(["project_member", "put", "--project_id", project_id, "--csv", csv_file, "--yes"])

    def test_list_project_member(self):
        main(["project_member", "list", "--project_id", project_id])

    def test_copy_project_member(self):
        main(["project_member", "copy", project_id, project_id, "--yes"])

    def test_invite_project_member(self):
        main(["project_member", "invite", "--user_id", user_id, "--role", "owner", "--project_id", project_id])

    def test_change_project_member(self):
        main(
            [
                "project_member",
                "change",
                "--all_user",
                "--project_id",
                project_id,
                "--member_info",
                '{"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}',
                "--yes",
            ]
        )


class TestStatistics:
    def test_visualize(self):
        output_dir = str(out_path / "statistics")
        main(
            [
                "statistics",
                "visualize",
                "--project_id",
                project_id,
                "--task_query",
                '{"status": "complete"}',
                "--output_dir",
                output_dir,
                "--minimal",
            ]
        )

    def test_merge_visualization_dir(self):
        output_dir = str(out_path / "statistics/merge")
        main(
            [
                "statistics",
                "merge_visualization_dir",
                "--dir",
                str(data_path / "statistics/visualization-dir"),
                "--output_dir",
                output_dir,
                "--minimal",
            ]
        )

    def test_list_task_progress(self):
        out_file = str(out_path / "task-progress.csv")
        main(
            [
                "statistics",
                "list_task_progress",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_cumulative_labor_time(self):
        out_file = str(out_path / "cumulative-labor-time.csv")
        main(
            [
                "statistics",
                "list_cumulative_labor_time",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_annotation_count(self):
        output_dir = str(out_path / "statistics-list-annotation-count")
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
        main(
            [
                "statistics",
                "list_annotation_count",
                "--project_id",
                project_id,
                "--output_dir",
                output_dir,
                "--group_by",
                "input_data_id",
            ]
        )

    def test_summarize_task_count(self):
        out_file = str(out_path / "summariz-task-count.csv")
        main(
            [
                "statistics",
                "summarize_task_count",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )
        out_file = str(out_path / "summariz-task-count2.csv")
        main(
            [
                "statistics",
                "summarize_task_count",
                "--project_id",
                project_id,
                "--task_json",
                str(data_path / "task.json"),
                "--output",
                out_file,
            ]
        )

    def test_summarize_task_count_by_task_id(self):
        out_file = str(out_path / "summarize_task_count_by_task_id.csv")
        main(
            [
                "statistics",
                "summarize_task_count_by_task_id",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_summarize_task_count_by_user(self):
        out_file = str(out_path / "summarize_task_count_by_user.csv")
        main(
            [
                "statistics",
                "summarize_task_count_by_user",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_by_date_user(self):
        out_file = str(out_path / "list_by_date_user.csv")
        main(
            [
                "statistics",
                "list_by_date_user",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_labor_time_per_user(self):
        out_file = str(out_path / "list_labor_time_per_user.csv")
        main(
            [
                "statistics",
                "list_labor_time_per_user",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )


class TestTaskHistory:
    command_name = "task_history"

    def test_list_with_json(self):
        out_file = str(out_path / "task.csv")

        main(
            [
                self.command_name,
                "list_with_json",
                "--project_id",
                project_id,
                "--task_id",
                "test1",
                "test2",
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_list_task_history(self):
        out_file = str(out_path / "task_history.csv")
        main(
            [
                self.command_name,
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--format",
                "csv",
                "--output",
                out_file,
            ]
        )


class TestExperimental:
    command_name = "experimental"

    def test_list_labor_worktime(self):
        out_file = str(out_path / "list_labor_worktime.csv")
        main(
            [
                self.command_name,
                "list_labor_worktime",
                "--project_id",
                project_id,
                "--start_date",
                "2020-07-01",
                "--end_date",
                "2020-07-02",
                "--output",
                str(out_file),
                "--yes",
            ]
        )

    def test_dashboad(self):
        out_file = str(out_path / "dashboard.csv")
        main(
            [
                self.command_name,
                "dashboard",
                "--project_id",
                project_id,
                "--date",
                "2020-07-01",
                "--output",
                str(out_file),
                "--yes",
            ]
        )
