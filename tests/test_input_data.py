import configparser
import datetime
import json
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

data_dir = Path("./tests/data/input_data")
out_dir = Path("./tests/out/input_data")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
annofab_service = annofabapi.build()


class TestCommandLine__put:
    def test_put_input_data__with_json__duplicated_input_data_path__error(self):
        json_args = [
            {
                "input_data_name": "test1",
                "input_data_path": "file://tests/data/lenna.png",
            },
            {
                "input_data_name": "test2",
                "input_data_path": "file://tests/data/lenna.png",
            },
        ]
        with pytest.raises(Exception):  # noqa: B017
            main(
                [
                    "input_data",
                    "put",
                    "--project_id",
                    project_id,
                    "--json",
                    json.dumps(json_args),
                    "--overwrite",
                    "--yes",
                    "--parallelism",
                    "2",
                ]
            )

    def test_put_input_data__with_json__duplicated_input_data_name__error(self):
        json_args = [
            {
                "input_data_name": "test1",
                "input_data_path": "file://tests/data/lenna1.png",
            },
            {
                "input_data_name": "test1",
                "input_data_path": "file://tests/data/lenna2.png",
            },
        ]
        with pytest.raises(Exception):  # noqa: B017
            main(
                [
                    "input_data",
                    "put",
                    "--project_id",
                    project_id,
                    "--json",
                    json.dumps(json_args),
                    "--overwrite",
                    "--yes",
                    "--parallelism",
                    "2",
                ]
            )


class TestCommandLine__put_with_json:
    @pytest.mark.submitting_job
    def test_put_input_data_with_zip(self):
        # 注意：ジョブ登録される
        zip_file = str(data_dir / "lenna.zip")
        main(
            [
                "input_data",
                "put_with_zip",
                "--project_id",
                project_id,
                "--zip",
                zip_file,
                "--wait",
                "--yes",
            ]
        )


class TestCommandLine:
    def test_scenario(self):
        input_data_id = f"test-{datetime.datetime.now().timestamp()!s}"

        json_args = [
            {
                "input_data_name": f"{input_data_id}--input_data_name",
                "input_data_path": "file://tests/data/small-lenna.png",
                "input_data_id": input_data_id,
            }
        ]
        main(
            [
                "input_data",
                "put",
                "--project_id",
                project_id,
                "--json",
                json.dumps(json_args),
                "--yes",
            ]
        )
        assert annofab_service.wrapper.get_input_data_or_none(project_id, input_data_id) is not None

        # 入力データ名の変更
        new_input_data_name = f"{input_data_id}--new_name"
        json_args_for_change_name = [{"input_data_id": input_data_id, "input_data_name": new_input_data_name}]

        main(
            [
                "input_data",
                "change_name",
                "--project_id",
                project_id,
                "--json",
                json.dumps(json_args_for_change_name),
                "--yes",
            ]
        )
        input_data, _ = annofab_service.api.get_input_data(project_id, input_data_id)
        assert input_data["input_data_name"] == new_input_data_name

        # メタデータの更新
        main(
            [
                "input_data",
                "update_metadata",
                "--project_id",
                project_id,
                "--input_data_id",
                input_data_id,
                "--metadata",
                '{"attr1":"foo"}',
                "--yes",
            ]
        )
        input_data, _ = annofab_service.api.get_input_data(project_id, input_data_id)
        assert input_data["metadata"] == {"attr1": "foo"}

        # メタデータのキーの削除
        main(
            [
                "input_data",
                "delete_metadata_key",
                "--project_id",
                project_id,
                "--input_data_id",
                input_data_id,
                "--metadata_key",
                "attr1",
                "--yes",
            ]
        )
        input_data, _ = annofab_service.api.get_input_data(project_id, input_data_id)
        assert input_data["metadata"] == {}

        # 入力データの削除
        main(["input_data", "delete", "--project_id", project_id, "--input_data_id", input_data_id, "--yes"])
        assert annofab_service.wrapper.get_input_data_or_none(project_id, input_data_id) is None

    def test_download(self):
        out_file = str(out_dir / "input_data-download.json")
        main(
            [
                "input_data",
                "download",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_input_data(self):
        out_file = str(out_dir / "input_data.json")
        main(
            [
                "input_data",
                "list",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_with_json(self):
        out_file = str(out_dir / "list_all_input_data.csv")
        main(
            [
                "input_data",
                "list_all",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_input_data_merged_task(self):
        out_file = str(out_dir / "input_data.csv")
        main(
            [
                "input_data",
                "list_all_merged_task",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )
