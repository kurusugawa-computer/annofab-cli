import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/supplementary")
out_dir = Path("./tests/out/supplementary")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_put_supplementar(self):
        main(
            [
                "supplementary",
                "put",
                "--project_id",
                project_id,
                "--csv",
                str(data_dir / "supplementary.csv"),
                "--overwrite",
                "--yes",
            ]
        )

    def test_list_supplementary(self):
        main(["supplementary", "list", "--project_id", project_id, "--input_data_id", "foo"])

    def test_delete_supplementar(self):
        main(
            [
                "supplementary",
                "delete",
                "--project_id",
                project_id,
                "--csv",
                str(data_dir / "deleted-supplementary.csv"),
                "--yes",
            ]
        )
