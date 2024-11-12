import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

out_dir = Path("./tests/out/job")
data_dir = Path("./tests/data/job")

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_delete(self):
        main(
            [
                "job",
                "delete",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
                "--job_id",
                "not_exists_job_id",
            ]
        )

    def test_list_job(self):
        main(
            [
                "job",
                "list",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
                "--format",
                "csv",
                "--output",
                str(out_dir / "list-out.csv"),
            ]
        )

    def test_list_last_job(self):
        main(
            [
                "job",
                "list_last",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
                "--format",
                "csv",
                "--output",
                str(out_dir / "list_last-out.csv"),
            ]
        )

    def test_wait(self):
        main(
            [
                "job",
                "wait",
                "--project_id",
                project_id,
                "--job_type",
                "gen-annotation",
            ]
        )
