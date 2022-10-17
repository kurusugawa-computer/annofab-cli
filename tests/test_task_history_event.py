import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main
import pytest
# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/task_history_event")
data_dir = Path("./tests/data/task_history_event")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
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
                "task_history_event",
                "download",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "download.json"),
            ]
        )

    def test_list_all(self):
        main(
            [
                "task_history_event",
                "list_all",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_all-out.csv"),
                "--format",
                "csv",
            ]
        )

    def test_list_worktime(self):
        main(
            [
                "task_history_event",
                "list_worktime",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list_worktime-out.csv"),
                "--format",
                "csv",
            ]
        )
