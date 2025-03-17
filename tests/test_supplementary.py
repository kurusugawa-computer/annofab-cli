import configparser
import datetime
import json
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


data_dir = Path("./tests/data/supplementary")
out_dir = Path("./tests/out/supplementary")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
input_data_id = annofab_config["input_data_id"]
annofab_service = annofabapi.build()


class TestCommandLine:
    @pytest.fixture
    def target_input_data(self):
        """シナリオテスト用の入力データを作成する

        Yields:
            作成した入力データ

        """
        new_input_data_id = f"test-{int(datetime.datetime.now().timestamp())!s}"
        # 入力データの作成
        input_data = annofab_service.wrapper.put_input_data_from_file(project_id, new_input_data_id, file_path="tests/data/small-lenna.png")
        yield input_data
        # 入力データの削除
        annofab_service.api.delete_input_data(project_id, new_input_data_id)

    def test_scenario(self, target_input_data):
        input_data_id = target_input_data["input_data_id"]
        json_args = [
            {
                "input_data_id": input_data_id,
                "supplementary_data_name": "foo-data",
                "supplementary_data_path": "file://tests/data/small-lenna.png",
            }
        ]
        str_json_args = json.dumps(json_args)

        # 補助情報の作成
        main(
            [
                "supplementary",
                "put",
                "--project_id",
                project_id,
                "--json",
                str_json_args,
                "--overwrite",
                "--yes",
            ]
        )

        supplementary_data_list, _ = annofab_service.api.get_supplementary_data_list(project_id, input_data_id)
        assert len(supplementary_data_list) == 1

        # 補助情報のリストを出力
        main(
            [
                "supplementary",
                "list",
                "--project_id",
                project_id,
                "--input_data_id",
                input_data_id,
                "--output",
                str(out_dir / "list.csv"),
                "--yes",
            ]
        )

        # 補助情報の削除
        json_args_delete = [
            {
                "input_data_id": input_data_id,
                "supplementary_data_id": supplementary_data_list[0]["supplementary_data_id"],
            }
        ]
        main(["supplementary", "delete", "--project_id", project_id, "--json", json.dumps(json_args_delete), "--yes"])
        supplementary_data_list, _ = annofab_service.api.get_supplementary_data_list(project_id, input_data_id)
        assert len(supplementary_data_list) == 0
