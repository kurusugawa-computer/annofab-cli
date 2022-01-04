import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    command_name = "experimental"

    def test_list_labor_worktime(self):
        out_file = str(out_dir / "list_labor_worktime.csv")
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

    def test_list_labor_worktime_from_csv(self):
        out_file = str(out_dir / "list_labor_worktime.csv")
        main(
            [
                self.command_name,
                "list_labor_worktime_from_csv",
                "--csv",
                str(test_dir / "list_labor_worktime/intermediate.csv"),
                "--format",
                "total",
                "--output",
                str(out_file),
            ]
        )

    def test_dashboad(self):
        out_file = str(out_dir / "dashboard.csv")
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
