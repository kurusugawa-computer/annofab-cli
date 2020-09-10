import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.project.list_project import ListProjectMain

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/project")
out_dir = Path("./tests/out/project")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build_from_netrc()


class TestListProject:
    @classmethod
    def setup_class(cls):
        cls.main_obj = ListProjectMain(service)

    def test_get_project_list_from_project_id(self):
        actual = self.main_obj.get_project_list_from_project_id([project_id])
        print(actual)

    def test_get_project_list_from_organization(self):
        organization, _ = service.api.get_organization_of_project(project_id)
        actual = self.main_obj.get_project_list_from_organization(organization["organization_name"])
        print(actual)
