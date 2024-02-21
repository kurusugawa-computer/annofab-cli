import configparser
import datetime
import json
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

out_dir = Path("./tests/out/comment")
data_dir = Path("./tests/data/comment")

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
        new_task_id = f"test-{int(datetime.datetime.now().timestamp())!s}"
        task, _ = service.api.put_task(project_id, new_task_id, request_body={"input_data_id_list": [input_data_id]})

        yield task
        # タスクの削除
        service.api.delete_task(project_id, new_task_id)

    def test_scenario_onhold_comment(self, target_task):
        """
        保留コメントに関するシナリオテスト。
        """

        project, _ = service.api.get_project(project_id)
        assert project["input_data_type"] == "image", "画像プロジェクトでないと、検査コメントコマンドのテストは実行できません。"

        task_id = target_task["task_id"]
        input_data_id = target_task["input_data_id_list"][0]

        # put_onhold_simply
        main(
            [
                "comment",
                "put_onhold_simply",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                "test with 'put_onhold_simply'",
                "--yes",
            ]
        )

        # put_onhold
        dict_comments = {
            task_id: {
                input_data_id: [
                    {
                        "comment": "test with 'put_onhold'",
                    }
                ]
            }
        }
        main(["comment", "put_onhold", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        # 保留コメントが登録されたかを確認
        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        onhold_comment_list = [e for e in comment_list if e["comment_type"] == "onhold"]
        assert len(onhold_comment_list) == 2

        # list command
        main(
            [
                "comment",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment_type",
                "onhold",
                "--output",
                str(out_dir / "list-onhold-out.csv"),
            ]
        )

        # delete command
        dict_comments = {task_id: {input_data_id: [e["comment_id"] for e in onhold_comment_list]}}
        main(["comment", "delete", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        # コメントが削除されているかを確認する
        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        onhold_comment_list = [e for e in comment_list if e["comment_type"] == "onhold"]
        assert len(onhold_comment_list) == 0

    def test_scenario_inspection_comment(self, target_task):
        """
        検査コメントに関するシナリオテスト。
        """
        project, _ = service.api.get_project(project_id)
        assert project["input_data_type"] == "image", "画像プロジェクトでないと、検査コメントコマンドのテストは実行できません。"

        task_id = target_task["task_id"]
        input_data_id = target_task["input_data_id_list"][0]

        # 検査/受入フェーズにして、検査コメントを付与できるようにする
        main(
            [
                "task",
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--phase",
                "annotation",
                "--yes",
            ]
        )

        task, _ = service.api.get_task(project_id, task_id)
        # アノテーション仕様に全体ラベルがあって属性が必須だと、タスクを次の状態に遷移させられないので、ここで確認する
        assert task["phase"] in {"inspection", "acceptance"}
        # 抜き取り検査率/受入率が設定されていると、完了状態になっている可能性があるので確認する
        assert task["status"] == "not_started"

        # put_inspection_simply
        main(
            [
                "comment",
                "put_inspection_simply",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                "test with 'put_inspection_simply'",
                "--yes",
            ]
        )

        # put_inspection command
        dict_comments = {
            task_id: {
                input_data_id: [
                    {
                        "comment": "test with 'put_inspection'",
                        "data": {"x": 10, "y": 20, "_type": "Point"},
                    }
                ]
            }
        }
        main(["comment", "put_inspection", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        # 検査コメントが登録されたことの確認
        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        inspection_comment_list = [e for e in comment_list if e["comment_type"] == "inspection"]
        assert len(inspection_comment_list) == 2

        # list command
        main(
            [
                "comment",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment_type",
                "inspection",
                "--output",
                str(out_dir / "list-inspection-out.csv"),
            ]
        )

        # delete command
        dict_comments = {task_id: {input_data_id: [e["comment_id"] for e in inspection_comment_list]}}
        main(["comment", "delete", "--project_id", project_id, "--json", json.dumps(dict_comments), "--yes"])

        comment_list, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": 2})
        inspection_comment_list = [e for e in comment_list if e["comment_type"] == "inspection"]
        assert len(inspection_comment_list) == 0

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
                "list_all",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "list-all-comment.csv"),
            ]
        )
