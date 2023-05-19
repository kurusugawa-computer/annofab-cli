import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/project_member")
data_dir = Path("./tests/data/project_member")

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_change(self):
        main(
            [
                "project_member",
                "change",
                "--all_user",
                "--project_id",
                project_id,
                "--member_info",
                '{"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}',
                "--yes",
            ]
        )

    def test_copy(self):
        main(["project_member", "copy", project_id, project_id, "--yes"])

    def test_delete(self):
        main(["project_member", "delete", "--project_id", project_id, "--user_id", "not_exists_user_id", "--yes"])

    def test_invite_project_member(self):
        user_id = service.api.login_user_id
        main(["project_member", "invite", "--user_id", user_id, "--role", "owner", "--project_id", project_id])

    def test_list_project_member(self):
        main(["project_member", "list", "--project_id", project_id])

    def test_put_project_member(self):
        csv_file = str(data_dir / "project_members.csv")
        main(["project_member", "put", "--project_id", project_id, "--csv", csv_file, "--yes"])
