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
