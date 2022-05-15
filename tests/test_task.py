import more_itertools
import configparser
import datetime
import json
import os
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main
from annofabcli.task.change_operator import ChangeOperatorMain
from tests.utils_for_test import set_logger

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/task")
out_dir = Path("./tests/out/task")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
input_data_id = annofab_config["input_data_id"]
service = annofabapi.build()

set_logger()


class TestChangeOperator:
    @classmethod
    def setup_class(cls):
        cls.main_obj = ChangeOperatorMain(service, all_yes=True)

    def test_change_operator_for_task(self):
        actual = self.main_obj.change_operator_for_task(project_id=project_id, task_id=task_id, new_account_id=None)

    def test_change_operator(self):
        actual = self.main_obj.change_operator(
            project_id=project_id, task_id_list=[task_id], new_user_id=service.api.login_user_id
        )


class TestCommandLine:
    command_name = "task"
    user_id = service.api.login_user_id

    def test_cancel_acceptance(self):
        main([self.command_name, "cancel_acceptance", "--project_id", project_id, "--task_id", task_id, "--yes"])

    def test_change_operator(self):
        # user指定
        main(
            [
                self.command_name,
                "change_operator",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--user_id",
                self.user_id,
                "--yes",
            ]
        )

        # 未割り当て
        main(
            [
                self.command_name,
                "change_operator",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--not_assign",
                "--yes",
            ]
        )

    def test_delete_task(self):
        main([self.command_name, "delete", "--project_id", project_id, "--task_id", "not-exists-task", "--yes"])

    def test_list(self):
        out_file = str(out_dir / "task.csv")
        main(
            [
                self.command_name,
                "list",
                "--project_id",
                project_id,
                "--task_query",
                f'{{"user_id": "{self.user_id}", "phase":"acceptance", "status": "complete"}}',
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_list_added_task_history(self):
        out_file = str(out_dir / "task.csv")
        main(
            [
                self.command_name,
                "list",
                "--project_id",
                project_id,
                "--task_query",
                f'{{"user_id": "{self.user_id}", "phase":"acceptance", "status": "complete"}}',
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_list_added_task_history_with_downloading(self):
        out_file = str(out_dir / "task.csv")
        main(
            [
                self.command_name,
                "list_added_task_history",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_merged_task_with_json(self):
        out_file = str(out_dir / "task.csv")
        main(
            [
                self.command_name,
                "list_added_task_history",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_with_json(self):
        out_file = str(out_dir / "task.csv")

        main(
            [
                self.command_name,
                "list_with_json",
                "--project_id",
                project_id,
                "--task_query",
                '{"status":"not_started"}',
                "--task_id",
                "test1",
                "test2",
                "--output",
                out_file,
                "--format",
                "csv",
            ]
        )

    def test_reject_task(self):
        main(
            [
                self.command_name,
                "reject",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                "テストコメント",
                "--yes",
            ]
        )

    def test_update_metadata(self):
        main(
            [
                self.command_name,
                "update_metadata",
                "--project_id",
                project_id,
                "--metadata",
                '{"attr1":"foo"}',
                "--task_id",
                task_id,
                "--yes",
            ]
        )

    def test_put_task_with_json(self):
        json_args = {"foo": ["bar"]}
        main([self.command_name, "put", "--project_id", project_id, "--json", json.dumps(json_args)])

    def test_copy_task_and_delete_task(self):
        copy_task_id = "copy-" + task_id
        main(
            [
                self.command_name,
                "copy",
                "--project_id",
                project_id,
                "--input",
                f"{task_id}:{copy_task_id}",
                "--yes",
            ]
        )

        main([self.command_name, "delete", "--project_id", project_id, "--task_id", copy_task_id, "--yes"])

    @pytest.mark.submitting_job
    def test_put_task_by_count(self):
        main(
            [
                self.command_name,
                "put_by_count",
                "--project_id",
                project_id,
                "--task_id_prefix",
                "sample",
                "--input_data_count",
                "10",
                "--wait",
            ]
        )

    def test_complete_task(self):
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--phase",
                "annotation",
                "--reply_comment",
                "対応しました（自動投稿）",
                "--yes",
            ]
        )

    @pytest.fixture
    def target_task(self):
        """シナリオテスト用のタスクを作成する

        Yields:
            作成したタスク
        """
        # タスクの作成
        new_task_id = f"test-{str(datetime.datetime.now().timestamp())}"
        task, _ = service.api.put_task(project_id, new_task_id, request_body={"input_data_id_list": [input_data_id]})
        yield task
        # タスクの削除
        service.api.delete_task(project_id, new_task_id)

    def test_scenario_phase_transition(self, target_task):
        """
        フェーズ遷移を確認するテスト

        Args:
            作成直後のタスク

        """
        project, _ = service.api.get_project(project_id)
        number_of_inspections = project["configuration"]["number_of_inspections"]
        assert number_of_inspections == 0, "プロジェクト設定の検査回数が0でないと、タスクのフェーズの遷移を確認するテストを実行できません。"

        task_id = target_task["task_id"]

        # タスクの提出（教師付→受入）
        main(
            [
                self.command_name,
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
        assert task["phase"] == "acceptance"

        # タスクの差し戻し
        main(
            [
                self.command_name,
                "reject",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--comment",
                "枠が付いていません（自動テストによるコメント）",
                "--yes",
            ]
        )
        task, _ = service.api.get_task(project_id, task_id)
        assert task["phase"] == "annotation"
        comments, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": "2"})
        assert len(comments) == 1

        # タスクの再提出（教師付→受入）
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--phase",
                "annotation",
                "--reply_comment",
                "対応しました（自動テストによるコメント）",
                "--yes",
            ]
        )
        task, _ = service.api.get_task(project_id, task_id)
        assert task["phase"] == "acceptance"
        comments, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": "2"})
        # 返信コメントの数だけ、コメントの数が増える
        assert len(comments) == 2

        # タスクを合格にする（受入未着手→受入完了）
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--phase",
                "acceptance",
                "--inspection_status",
                "resolved",
                "--yes",
            ]
        )
        task, _ = service.api.get_task(project_id, task_id)
        assert task["status"] == "complete"
        comments, _ = service.api.get_comments(project_id, task_id, input_data_id, query_params={"v": "2"})
        target_comment = more_itertools.first_true(comments, pred=lambda e:e["comment_node"]["_type"] == "Root")
        assert target_comment["comment_node"]["status"] == "resolved"

        # タスクの受入取り消し
        main([self.command_name, "cancel_acceptance", "--project_id", project_id, "--task_id", task_id, "--yes"])
        task, _ = service.api.get_task(project_id, task_id)
        assert task["status"] == "not_started"

    def test_main(self):
        """
        `task reject`コマンドなどタスクのフェーズや状態によって実行できないコマンドのテスト。
        タスクの作成から、タスクのフェーズを遷移させて、最後に削除する
        """
        task, _ = service.api.get_task(project_id, task_id)
        input_data_id = task["input_data_id_list"][0]

        # タスクの作成
        new_task_id = str(datetime.datetime.now().timestamp())
        json_args = {new_task_id: [input_data_id]}
        main([self.command_name, "put", "--project_id", project_id, "--json", json.dumps(json_args), "--yes"])

        # タスクの提出
        main(
            [
                self.command_name,
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

        # タスクの差し戻し
        main(
            [
                self.command_name,
                "reject",
                "--project_id",
                project_id,
                "--task_id",
                new_task_id,
                "--comment",
                "指摘（自動コメント）",
                "--yes",
            ]
        )

        # タスクの再提出
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                new_task_id,
                "--reply_comment",
                "返信（自動コメント）",
                "--phase",
                "annotation",
                "--yes",
            ]
        )

        # タスクの再提出(検査フェーズ)
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                new_task_id,
                "--phase",
                "inspection",
                "--inspection_status",
                "closed",
                "--yes",
            ]
        )

        # タスクの再提出(受入フェーズ)
        main(
            [
                self.command_name,
                "complete",
                "--project_id",
                project_id,
                "--task_id",
                new_task_id,
                "--phase",
                "acceptance",
                "--inspection_status",
                "closed",
                "--yes",
            ]
        )

        # タスクの再提出(受入フェーズ)
        main([self.command_name, "cancel_acceptance", "--project_id", project_id, "--task_id", new_task_id, "--yes"])

        # タスクの削除
        main([self.command_name, "delete", "--project_id", project_id, "--task_id", new_task_id, "--force", "--yes"])
