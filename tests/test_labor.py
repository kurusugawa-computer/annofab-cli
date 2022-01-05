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
    def test_list_worktime_with_project_id(self):
        output_file = out_dir / "labor/list_worktime.csv"
        main(
            [
                "labor",
                "list_worktime",
                "--project_id",
                project_id,
                "--user_id",
                service.api.login_user_id,
                "--start_date",
                "2019-09-01",
                "--end_date",
                "2019-09-01",
                "--output",
                str(output_file),
            ]
        )

    def test_list_worktime_with_organization_name(self):
        output_file = out_dir / "labor/list_worktime2.csv"
        main(
            [
                "labor",
                "list_worktime",
                "--organization",
                organization_name,
                "--user_id",
                service.api.login_user_id,
                "--start_date",
                "2019-09-01",
                "--end_date",
                "2019-09-01",
                "--output",
                str(output_file),
            ]
        )
