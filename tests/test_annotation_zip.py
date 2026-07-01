import configparser
from pathlib import Path

import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/annotation_zip")
out_dir.mkdir(exist_ok=True, parents=True)


inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]


class TestCommandLine:
    def test_list_annotation_attribute(self):
        main(
            [
                "annotation_zip",
                "list_annotation_attribute",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "test_list_annotation_attribute-out.csv"),
                "--format",
                "csv",
            ]
        )
