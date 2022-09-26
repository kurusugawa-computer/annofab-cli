import configparser
import datetime
import json
import os
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

out_dir = Path("./tests/out/inspection_comment")
data_dir = Path("./tests/data/inspection_comment")

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
input_data_id = annofab_config["input_data_id"]
service = annofabapi.build()


class TestCommandLine:
    @pytest.fixture
    def target_task(self):
        """シナリオテスト用のタスクを作成する

        Yields:
            作成したタスク
        """
        # タスクの作成
        new_task_id = f"test-{str(int(datetime.datetime.now().timestamp()))}"
        task, _ = service.api.put_task(project_id, new_task_id, request_body={"input_data_id_list": [input_data_id]})

        # 検査/受入フェーズにして、検査コメントを付与できるようにする
        main(
            [
                "task",
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                new_task_id,
                "--phase",
                "annotation",
                "--yes",
            ]
        )

        yield task
        # タスクの削除
        service.api.delete_task(project_id, new_task_id)

    def test_scenario(self, target_task):
        """
        シナリオテスト。すべてのannotation系コマンドを実行する。
        前提条件：矩形の"car"ラベルに"truncation"チェックボックスが存在すること
        """

        project, _ = service.api.get_project(project_id)
        assert project["input_data_type"] == "image", "画像プロジェクトでないと、検査コメントコマンドのテストは実行できません。"

        task_id = target_task["task_id"]
        input_data_id = target_task["input_data_id_list"][0]

        # put_simply
        main(
            [
                "inspection_comment",
                "put_simply",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                "test with 'put_simply'",
                "--yes",
            ]
        )

        dict_comments = {
            task_id: {
                input_data_id: [
                    {
                        "comment": "test with 'put'",
                        "data": {"x": 10, "y": 20, "_type": "Point"},
                    }
                ]
            }
        }
        main(["inspection_comment", "put", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        inspection_comment_list = [e for e in comment_list if e["comment_type"] == "inspection"]
        assert len(inspection_comment_list) == 2

        # list command
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

        # delete command
        dict_comments = {task_id: {input_data_id: [e["comment_id"] for e in inspection_comment_list]}}
        main(["inspection_comment", "delete", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        inspection_comment_list = [e for e in comment_list if e["comment_type"] == "inspection"]
        assert len(inspection_comment_list) == 0

    def test_list_inspection_comment_with_json(self):
        main(
            [
                "inspection_comment",
                "list_all",
                "--project_id",
                project_id,
                "--exclude_reply",
                "--output",
                str(out_dir / "list_all-out.csv"),
            ]
        )
