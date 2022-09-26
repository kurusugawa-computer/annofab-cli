import configparser
import os
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main
from annofabcli.project.list_project import ListProjectMain

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/project")
out_dir = Path("./tests/out/project")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()

organization_name = service.api.get_organization_of_project(project_id)[0]["organization_name"]


class TestCommandLine:
    def test_change_status(self):
        main(["project", "change_status", "--project_id", project_id, "--status", "active"])

    @pytest.mark.submitting_job
    def test_copy(self):
        main(["project", "copy", "--project_id", project_id, "--dest_title", "copy-project", "--wait", "--yes"])

    def test_diff_project(self):
        main(["project", "diff", project_id, project_id, "--target", "annotation_labels"])

    def test_download(self):
        out_file = str(out_dir / "task.json")
        main(["project", "task", "download", "--project_id", project_id, "--output", out_file])

    def test_list(self):
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
                str(out_dir / "project-list-from-organization.csv"),
            ]
        )

    @pytest.mark.submitting_job
    def test_update_annotation_zip(self):
        main(["project", "update_annotation_zip", "--project_id", project_id, "--wait"])


class TestListProject:
    @classmethod
    def setup_class(cls):
        cls.main_obj = ListProjectMain(service)

    def test_get_project_list_from_project_id(self):
        actual = self.main_obj.get_project_list_from_project_id([project_id])

    def test_get_project_list_from_organization(self):
        actual = self.main_obj.get_project_list_from_organization(organization_name)
