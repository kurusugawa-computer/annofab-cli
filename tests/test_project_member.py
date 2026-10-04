import configparser
import json
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


out_dir = Path("./tests/out/project_member")

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    def test_update(self):
        updates = [
            {"user_id": member["user_id"], "sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}
            for member in service.wrapper.get_all_project_members(project_id)
            if member["user_id"] != service.api.login_user_id
        ]
        main(
            [
                "project_member",
                "update",
                "--project_id",
                project_id,
                "--json",
                json.dumps(updates),
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
