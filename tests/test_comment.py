import configparser
import os
from pathlib import Path

from annofabcli.__main__ import main

out_dir = Path("./tests/out/comment")
data_dir = Path("./tests/data/comment")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]


class TestCommandLine:
    def test_download(self):
        main(
            [
                "comment",
                "download",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "download.json"),
            ]
        )

    def test_list(self):
        main(
            [
                "comment",
                "list",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list-comment.csv"),
            ]
        )

    def test_list(self):
        main(
            [
                "comment",
                "list_all",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list-all-comment.csv"),
            ]
        )
