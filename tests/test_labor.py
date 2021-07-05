import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

out_dir = Path("./tests/out/labor")
data_dir = Path("./tests/data/labor")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()

organization_name = service.api.get_organization_of_project(project_id)[0]["organization_name"]


class TestCommandLine:
    def test_list_worktime_by_user_with_project_id(self):
        output_dir = str(out_dir / "labor")
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
        output_dir = str(out_dir / "labor")
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
