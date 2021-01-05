import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/organization_member")
out_dir = Path("./tests/out/organization_member")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build()

organization_name = service.api.get_organization_of_project(project_id)[0]["organization_name"]


class TestCommandLine:
    def test_list_organization_member(self):
        out_file = str(out_dir / "organization_member.csv")
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
