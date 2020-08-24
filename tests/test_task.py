import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.task.change_operator import ChangeOperatorMain
from tests.utils_for_test import set_logger

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/task")
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
        print(actual)

    def test_change_operator(self):
        actual = self.main_obj.change_operator(
            project_id=project_id, task_id_list=[task_id], new_user_id=service.api.login_user_id
        )
        print(actual)
