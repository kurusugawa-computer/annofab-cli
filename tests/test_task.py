import configparser
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
                "--task_id",
                task_id,
                "--dest_task_id",
                copy_task_id,
                "--yes",
            ]
        )

        main([self.command_name, "delete", "--project_id", project_id, "--task_id", "not-exists-task", "--yes"])

    @pytest.mark.submitting_job
    def test_put_task_with_csv(self):
        csv_file = str(data_dir / "put_task.csv")
        main([self.command_name, "put", "--project_id", project_id, "--csv", csv_file, "--wait"])

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
