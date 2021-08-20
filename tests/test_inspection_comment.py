import configparser
import json
import os
from pathlib import Path

import annofabapi

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
    @classmethod
    def setup_class(cls):
        annofab_service = annofabapi.build()
        task, _ = annofab_service.api.get_task(project_id, task_id)
        cls.input_data_id = task["input_data_id_list"][0]

    def test_delete_inspection_comment(self):
        dict_comments = {task_id: {self.input_data_id: ["foo", "bar"]}}
        main(["inspection_comment", "delete", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

    def test_list_inspection_comment(self):
        main(
            [
                "inspection_comment",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                str(out_dir / "list-out.csv"),
            ]
        )

    def test_list_inspection_comment_with_json(self):
        main(
            [
                "inspection_comment",
                "list_with_json",
                "--project_id",
                project_id,
                "--exclude_reply",
                "--output",
                str(out_dir / "list_with_json-out.csv"),
            ]
        )

    def test_put_inspection_comment(self):
        dict_comments = {
            task_id: {
                self.input_data_id: [
                    {
                        "comment": "test comment",
                        "data": {"x": 10, "y": 20, "_type": "Point"},
                    }
                ]
            }
        }

        main(["inspection_comment", "put", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])
