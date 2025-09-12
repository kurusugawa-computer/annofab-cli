import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


data_dir = Path("./tests/data/project")
out_dir = Path("./tests/out/project")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    """
    Notes:
        `project put`のテストは無視する。プロジェクトを作成した後、削除する手段がないため。
    """

    organization_name: str

    @classmethod
    def setup_class(cls):
        cls.organization_name = service.api.get_organization_of_project(project_id)[0]["organization_name"]

    def test_change_status(self):
        main(["project", "change_status", "--project_id", project_id, "--status", "active"])

    @pytest.mark.submitting_job
    def test_copy(self):
        main(["project", "copy", "--project_id", project_id, "--dest_title", "copy-project", "--yes"])

    def test_diff_project(self):
        main(["project", "diff", project_id, project_id, "--target", "annotation_labels"])

    def test_list(self):
        main(
            [
                "project",
                "list",
                "--organization",
                self.organization_name,
                "--project_query",
                '{"status": "active"}',
                "--format",
                "csv",
                "--output",
                str(out_dir / "project-list-from-organization.csv"),
            ]
        )

    def test_update_configuration(self):
        # 簡単な設定更新のテスト
        # 実際の設定変更を行うため、元の設定に影響しない軽微な変更をテストする
        main(["project", "update_configuration", "--project_id", project_id, "--configuration", '{"editor_version": "preview"}', "--yes"])
