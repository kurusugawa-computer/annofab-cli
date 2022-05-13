from __future__ import annotations

import configparser
import datetime
import json
import os
import tempfile
import time
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/annotation")
out_dir = Path("./tests/out/annotation")
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


class TestCommandLine:
    def _validate_annotation_specs(self):
        annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        labels = annotation_specs["labels"]

    def test_scenario(self):
        """
        シナリオテスト。すべてのannotation系コマンドを実行する。
        前提条件：矩形の"car"ラベルに"truncation"チェックボックスが存在すること
        """
        # タスクの作成
        new_task_id = f"test-{str(datetime.datetime.now().timestamp())}"
        service.api.put_task(project_id, new_task_id, request_body={"input_data_id_list": [input_data_id]})

        # インポート用のアノテーションを生成して、アノテーションをインポートする
        self._execute_import(new_task_id, input_data_id)

        print("すぐに`api.get_annotation_list`を実行すると、インポートしたアノテーションが含まれないので、数秒待つ")
        time.sleep(3)

        # list系のコマンドのテスト
        self._execute_list(new_task_id)

        # copyコマンドのテスト
        self._execute_copy(new_task_id, input_data_id)

        # 属性とプロパティの変更
        self._execute_change_properties_and_attributes(new_task_id, input_data_id)

        # アノテーションのダンプ、削除、リストア
        self._execute_dump_delete_restore(new_task_id, input_data_id)

        # タスクの削除
        service.api.delete_task(project_id, new_task_id)

    @pytest.mark.depending_on_annotation_specs
    def test_import_3dpc_annotation(self):
        project_id_of_3dpc = annofab_config["3dpc_project_id"]
        main(
            [
                "annotation",
                "import",
                "--project_id",
                project_id_of_3dpc,
                "--annotation",
                str(data_dir / "3dpc-simple-annotation"),
                "--overwrite",
                "--yes",
            ]
        )

    def write_simple_annotation(self, task_id: str, input_data_id: str, annotation_dir: Path):
        # インポート用のアノテーションを生成
        simple_annotation = {
            "details": [
                {
                    "label": "car",
                    "data": {
                        "left_top": {"x": 0, "y": 0},
                        "right_bottom": {"x": 100, "y": 100},
                        "_type": "BoundingBox",
                    },
                    "attributes": {"truncation": True},
                }
            ]
        }

        task_dir = annotation_dir / task_id
        input_data_json = task_dir / f"{input_data_id}.json"

        task_dir.mkdir(exist_ok=True, parents=True)
        with input_data_json.open("w", encoding="utf8") as f:
            json.dump(simple_annotation, f, ensure_ascii=False)

    def _execute_change_properties_and_attributes(self, task_id: str, input_data_id: str):
        """
        アノテーションのプロパティの変更、属性の変更のテスト
        """
        # truncation属性をFalseに変更する
        main(
            [
                "annotation",
                "change_attributes",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--annotation_query",
                '{"label_name_en":"car"}',
                "--attributes",
                '[{"additional_data_definition_name_en": "truncation", "flag": false}]',
                "--yes",
            ]
        )

        # 属性を確認するためにSimpleアノテーションを取得する
        simple_annotation, _ = service.api.get_annotation(project_id, task_id, input_data_id)
        detail = simple_annotation["details"][0]
        assert detail["attributes"]["truncation"] == False

        # is_protected プロパティを変更する
        main(
            [
                "annotation",
                "change_properties",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--properties",
                '{"is_protected":true}',
                "--yes",
            ]
        )

        editor_annotation, _ = service.api.get_editor_annotation(project_id, task_id, input_data_id)
        detail = editor_annotation["details"][0]
        assert detail["is_protected"] == True

    def _execute_dump_delete_restore(self, task_id: str, input_data_id: str):
        """
        アノテーションのダンプ、削除、リストアのテスト
        """
        with tempfile.TemporaryDirectory() as str_dump_dir:
            # アノテーション情報のダンプ
            main(
                [
                    "annotation",
                    "dump",
                    "--project_id",
                    project_id,
                    "--task_id",
                    task_id,
                    "--output_dir",
                    str_dump_dir,
                    "--yes",
                ]
            )

            # print("すぐに`annotation delete`を実行すると、'ALREADY UPDATED'で失敗する可能性があるので、数秒待つ")
            # time.sleep(3)

            # アノテーションの削除
            main(["annotation", "delete", "--project_id", project_id, "--task_id", task_id, "--yes"])
            editor_annotation, _ = service.api.get_editor_annotation(project_id, task_id, input_data_id)
            assert len(editor_annotation["details"]) == 0

            # アノテーションのリストア
            main(
                [
                    "annotation",
                    "restore",
                    "--project_id",
                    project_id,
                    "--task_id",
                    task_id,
                    "--annotation",
                    str_dump_dir,
                    "--yes",
                ]
            )
            editor_annotation, _ = service.api.get_editor_annotation(project_id, task_id, input_data_id)
            assert len(editor_annotation["details"]) == 1

    def _execute_import(self, task_id: str, input_data_id: str):
        """
        アノテーションのインポートのテスト
        """
        # インポート用のアノテーションを生成して、アノテーションをインポートする
        with tempfile.TemporaryDirectory() as str_temp_dir:
            annotation_dir = Path(str_temp_dir)
            self.write_simple_annotation(task_id, input_data_id, annotation_dir)

            main(["annotation", "import", "--project_id", project_id, "--annotation", str(annotation_dir), "--yes"])

        simple_annotation, _ = service.api.get_annotation(project_id, task_id, input_data_id)
        assert len(simple_annotation["details"]) == 1
        detail = simple_annotation["details"][0]
        detail["label"] == "car"
        detail["attributes"]["truncation"] == True

    def _execute_copy(self, src_task_id: str, input_data_id: str):
        """
        アノテーションのコピー
        """
        dest_task_id = f"{src_task_id}-copy"

        service.api.put_task(project_id, dest_task_id, request_body={"input_data_id_list": [input_data_id]})

        main(
            [
                "annotation",
                "copy",
                "--project_id",
                project_id,
                "--input",
                f"{src_task_id}:{dest_task_id}",
                "--yes",
                "--overwrite",
            ]
        )

        dest_editor_annotation, _ = service.api.get_editor_annotation(project_id, dest_task_id, input_data_id)
        assert len(dest_editor_annotation["details"]) == 1
        dest_detail = dest_editor_annotation["details"][0]

        src_editor_annotation, _ = service.api.get_editor_annotation(project_id, src_task_id, input_data_id)
        assert len(src_editor_annotation["details"]) == 1
        src_detail = src_editor_annotation["details"][0]

        assert src_detail == dest_detail

        service.api.delete_task(project_id, dest_task_id)

    def _execute_list(self, task_id: str):
        """
        list系のコマンドのテスト
        """
        main(
            [
                "annotation",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                str(out_dir / "annotation.csv"),
            ]
        )

        main(
            [
                "annotation",
                "list_count",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                str(out_dir / "annotation_count.csv"),
            ]
        )
