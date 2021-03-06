import configparser
import os
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/input_data")
out_dir = Path("./tests/out/input_data")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build()


class TestCommandLine:
    @classmethod
    def setup_class(cls):
        annofab_service = annofabapi.build()
        task, _ = annofab_service.api.get_task(project_id, task_id)
        cls.input_data_id = task["input_data_id_list"][0]

    def test_delete_input_data(self):
        main(["input_data", "delete", "--project_id", project_id, "--input_data_id", "foo", "--yes"])

    def test_list_input_data(self):
        out_file = str(out_dir / "input_data.json")
        main(
            [
                "input_data",
                "list",
                "--project_id",
                project_id,
                "--input_data_query",
                '{"input_data_name": "abcdefg"}',
                "--add_details",
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_merged_task(self):
        out_file = str(out_dir / "input_data.csv")
        main(
            [
                "input_data",
                "list_merged_task",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_with_json(self):
        out_file = str(out_dir / "input_data.csv")
        main(
            [
                "input_data",
                "list_with_json",
                "--project_id",
                project_id,
                "--input_data_query",
                '{"input_data_name": "abcdefg"}',
                "--input_data_id",
                "test1",
                "test2",
                "--output",
                out_file,
            ]
        )

    def test_put_input_data(self):
        csv_file = str(out_dir / "input_data2.csv")
        main(
            [
                "input_data",
                "put",
                "--project_id",
                project_id,
                "--csv",
                csv_file,
                "--overwrite",
                "--yes",
                "--parallelism",
                "2",
            ]
        )

    @pytest.mark.submitting_job
    def test_put_input_data_with_zip(self):
        # 注意：ジョブ登録される
        zip_file = str(data_dir / "lenna.zip")
        main(
            [
                "input_data",
                "put",
                "--project_id",
                project_id,
                "--zip",
                zip_file,
                "--wait",
                "--yes",
            ]
        )

    def test_update_metadata(self):
        main(
            [
                "input_data",
                "update_metadata",
                "--project_id",
                project_id,
                "--input_data_id",
                self.input_data_id,
                "--metadata",
                '{"attr1":"foo"}',
                "--yes",
            ]
        )
