import configparser
import datetime
import os
from pathlib import Path

import annofabapi
import pytest

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


class TestAnnotation:
    def test_annotation(self):
        main(
            [
                "annotation",
                "list_count",
                "--project_id",
                project_id,
                "--annotation_query",
                '{"label_name_en": "car"}',
                "--output",
                str(out_path / "annotation_count.csv"),
            ]
        )

    def test_dump_annotation(self):
        output_dir = str(out_path / "dump-annotation")
        main(
            ["annotation", "dump", "--project_id", project_id, "--task_id", task_id, "--output", output_dir, "--yes",]
        )

    def test_delete_and_restore_annotation(self):
        backup_dir = str(out_path / "backup-annotation")
        main(
            ["annotation", "delete", "--project_id", project_id, "--task_id", task_id, "--backup", backup_dir, "--yes",]
        )

        main(
            [
                "annotation",
                "restore",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--annotation",
                backup_dir,
                "--yes",
            ]
        )

    def test_import_annotation(self):
        main(
            [
                "annotation",
                "import",
                "--project_id",
                project_id,
                "--annotation",
                str(data_path / "imported-annotation.zip"),
                "--task_id",
                task_id,
                "--overwrite",
                "--yes",
            ]
        )


class TestAnnotationSpecs:
    command_name = "annotation_specs"

    def test_annotation_specs_histories(self):
        out_file = str(out_path / "anotaton_specs_histories.csv")
        main([self.command_name, "history", "--project_id", project_id, "--output", out_file])

    def test_annotation_specs_list_label(self):
        out_file = str(out_path / "anotation_specs_list_label.json")
        main([self.command_name, "list_label", "--project_id", project_id, "--output", out_file])

    def test_old_annotation_specs_list_label(self):
        out_file = str(out_path / "anotation_specs_list_label.json")
        main([self.command_name, "list_label", "--project_id", project_id, "--before", "1", "--output", out_file])

    def test_annotation_specs_list_label_from_history_id(self):
        out_file = str(out_path / "anotation_specs_list_label.json")
        histories, _ = service.api.get_annotation_specs_histories(project_id)
        history_id = histories[0]["history_id"]
        main(
            [
                self.command_name,
                "list_label",
                "--project_id",
                project_id,
                "--history_id",
                history_id,
                "--output",
                out_file,
            ]
        )

    def test_annotation_specs_list_label_color(self):
        out_file = str(out_path / "anotation_specs_list_label_color.json")
        main(
            [
                self.command_name,
                "list_label_color",
                "--project_id",
                project_id,
                "--format",
                "json",
                "--output",
                out_file,
            ]
        )


class TestFilesystem:
    def test_filesystem(self):
        zip_path = data_path / "simple-annotation.zip"
        output_image_dir = out_path / "annotation-image"
        label_color_file = data_path / "label_color.json"

        main(
            [
                "filesystem",
                "write_annotation_image",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_image_dir),
                "--image_size",
                "64x64",
                "--label_color",
                f"file://{str(label_color_file)}",
                "--image_extension",
                "jpg",
            ]
        )


class TestInputData:
    command_name = "input_data"

    def test_delete_input_data(self):
        main(["input_data", "delete", "--project_id", project_id, "--input_data_id", "foo", "--yes"])

    def test_list_input_data(self):
        out_file = str(out_path / "input_data.json")
        main(
            [
                "input_data",
                "list",
                "--project_id",
                project_id,
                "--input_data_query",
                '{"input_data_name": "abcdefg"}',
                "--add_details",
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_with_batch(self):
        out_file = str(out_path / "input_data.json")
        main(
            [
                "input_data",
                "list",
                "--project_id",
                project_id,
                "--input_data_query",
                '{"input_data_name": "abcdefg"}',
                "--batch",
                '{"first":"2019-01-01", "last":"2019-01-31", "days":7}',
                "--add_details",
                "--output",
                out_file,
            ]
        )

    def test_put_input_data(self):
        csv_file = str(data_path / "input_data2.csv")
        main(
            [
                self.command_name,
                "put",
                "--project_id",
                project_id,
                "--csv",
                csv_file,
                "--overwrite",
                "--yes",
                "--parallelism",
                "2",
            ]
        )

    @pytest.mark.submitting_job
    def test_put_input_data_with_zip(self):
        # 注意：ジョブ登録される
        zip_file = str(data_path / "lenna.zip")
        main(
            [
                self.command_name,
                "put",
                "--project_id",
                project_id,
                "--zip",
                zip_file,
                "--wait",
                "--yes",
                "--wait_options",
                '{"interval":1, "max_tries":1}',
            ]
        )


class TestInspectionComment:
    def test_list_inspection_comment(self):
        out_file = str(out_path / "inspection_comment.csv")
        main(["inspection_comment", "list", "--project_id", project_id, "--task_id", task_id, "--output", out_file])

    def test_list_inspection_comment_from_json(self):
        out_file = str(out_path / "inspection_comment.csv")
        inspection_comment_json = str(data_path / "inspection-comment.json")
        main(
            [
                "inspection_comment",
                "list",
                "--project_id",
                project_id,
                "--inspection_comment_json",
                inspection_comment_json,
                "--output",
                out_file,
            ]
        )

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

    def test_list_unprocessed_inspection_comment_from_json(self):
        out_file = str(out_path / "inspection_comment.csv")
        inspection_comment_json = str(data_path / "inspection-comment.json")
        main(
            [
                "inspection_comment",
                "list_unprocessed",
                "--project_id",
                project_id,
                "--inspection_comment_json",
                inspection_comment_json,
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
                "--availability",
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


class TestOrganizationMember:
    def test_list_organization_member(self):
        out_file = str(out_path / "organization_member.csv")
        main(
            [
                "organization_member",
                "list",
                "--organization",
                organization_name,
                "--format",
                "csv",
                "--output",
                out_file,
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
            ["project", "list", "--project_id", project_id, "--format", "csv", "--output", out_file,]
        )

    def test_update_annotation_zip(self):
        main(["project", "update_annotation_zip", "--project_id", project_id])


class TestProjectMember:
    def test_put_project_member(self):
        csv_file = str(data_path / "project_members.csv")
        main(["project_member", "put", "--project_id", project_id, "--csv", csv_file, "--yes"])

    def test_list_project_member(self):
        main(["project_member", "list", "--project_id", project_id])
        main(["project_member", "list", "--organization", organization_name])

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
            ]
        )

    def test_list_task_progress(self):
        out_file = str(out_path / "task-progress.csv")
        main(
            ["statistics", "list_task_progress", "--project_id", project_id, "--output", out_file,]
        )

    def test_list_cumulative_labor_time(self):
        out_file = str(out_path / "cumulative-labor-time.csv")
        main(
            ["statistics", "list_cumulative_labor_time", "--project_id", project_id, "--output", out_file,]
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


class TestSupplementary:
    def test_list_project_member(self):
        main(["supplementary", "list", "--project_id", project_id, "--input_data_id", "foo"])


class TestTask:
    command_name = "task"

    def test_cancel_acceptance(self):
        main([self.command_name, "cancel_acceptance", "--project_id", project_id, "--task_id", task_id, "--yes"])

    def test_change_operator(self):
        # user指定
        main(
            [
                self.command_name,
                "change_operator",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--user_id",
                user_id,
                "--yes",
            ]
        )

        # 未割り当て
        main(
            [
                self.command_name,
                "change_operator",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--not_assign",
                "--yes",
            ]
        )

    def test_delete_task(self):
        main([self.command_name, "delete", "--project_id", project_id, "--task_id", "not-exists-task", "--yes"])

    def test_list(self):
        out_file = str(out_path / "task.csv")
        main(
            [
                self.command_name,
                "list",
                "--project_id",
                project_id,
                "--task_query",
                f'{{"user_id": "{user_id}", "phase":"acceptance", "status": "complete"}}',
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_list_with_task_json(self):
        out_file = str(out_path / "task.csv")
        task_json = str(data_path / "task.json")

        main(
            [
                self.command_name,
                "list",
                "--project_id",
                project_id,
                "--task_json",
                task_json,
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_reject_task(self):
        inspection_comment = datetime.datetime.now().isoformat()
        main(
            [
                self.command_name,
                "reject",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                inspection_comment,
                "--yes",
            ]
        )

    @pytest.mark.submitting_job
    def test_put_task(self):
        csv_file = str(data_path / "put_task.csv")
        main(
            [self.command_name, "put", "--project_id", project_id, "--csv", csv_file,]
        )

    def test_complete_task(self):
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--phase",
                "annotation",
                "--reply_comment",
                "対応しました（自動投稿",
                "--yes",
            ]
        )
