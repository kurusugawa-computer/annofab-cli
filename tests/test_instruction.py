import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

out_dir = Path("./tests/out/instruction")
data_dir = Path("./tests/data/instruction")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build_from_netrc()


class TestCommandLine:
    def test_upload_instruction(self):
        html_file = str(data_dir / "instruction.html")
        main(["instruction", "upload", "--project_id", project_id, "--html", html_file])

    def test_copy_instruction(self):
        src_project_id = project_id
        dest_project_id = project_id
        main(["instruction", "copy", src_project_id, dest_project_id, "--yes"])

    def test_list_history(self):
        main(["instruction", "list_history", "--project_id", project_id, "--output", str(out_dir / "list_history-out.csv")])

    def test_download(self):
        main(["instruction", "download", "--project_id", project_id, "--output_dir", str(out_dir / "download-out"), "--download_image"])
