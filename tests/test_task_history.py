import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

out_dir = Path("./tests/out/task_history")
data_dir = Path("./tests/data/task_history")

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_download(self):
        main(
            [
                "task_history",
                "download",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "download.json"),
            ]
        )

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

    def test_list_all(self):
        main(
            [
                "task_history",
                "list_all",
                "--project_id",
                project_id,
                "--task_id",
                "test1",
                "test2",
                "--output",
                str(out_dir / "list_all-out.csv"),
                "--format",
                "csv",
            ]
        )
