import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

out_dir = Path("./tests/out/task_history")
data_dir = Path("./tests/data/task_history")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build_from_netrc()


class TestCommandLine:
    def test_list_task_history(self):

        main(
            [
                "task_history",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--format",
                "csv",
                "--output",
                str(out_dir / "list-out.csv"),
            ]
        )

    def test_list_with_json(self):
        main(
            [
                "task_history",
                "list_with_json",
                "--project_id",
                project_id,
                "--task_id",
                "test1",
                "test2",
                "--output",
                str(out_dir / "list_with_json-out.csv"),
                "--format",
                "csv",
            ]
        )
