import configparser
import os
from pathlib import Path

from annofabcli.__main__ import main

out_dir = Path("./tests/out/inspection_comment")
data_dir = Path("./tests/data/inspection_comment")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]


class TestCommandLine:
    def test_list_inspection_comment(self):
        out_file = str(data_dir / "inspection_comment.csv")
        main(["inspection_comment", "list", "--project_id", project_id, "--task_id", task_id, "--output", out_file])

    def test_list_inspection_comment_with_json(self):
        out_file = str(data_dir / "inspection_comment.csv")
        main(
            [
                "inspection_comment",
                "list_with_json",
                "--project_id",
                project_id,
                "--exclude_reply",
                "--output",
                out_file,
            ]
        )
