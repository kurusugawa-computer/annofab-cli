from __future__ import annotations

import configparser
import datetime
import json
import tempfile
import time
from pathlib import Path

import annofabapi
import more_itertools
import pytest
from annofabapi.util.annotation_specs import get_english_message

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi


data_dir = Path("./tests/data/annotation")
out_dir = Path("./tests/out/annotation")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
input_data_id = annofab_config["input_data_id"]
service = annofabapi.build()


class TestCommandLine:
    def _validate_annotation_specs_for_scenario_test(self):
        """シナリオテストを実行できるアノテーション仕様かどうかを判定する

        Rreturns:
            Trueならシナリオテストを実行できるアノテーション仕様
        """
        annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params={"v": "2"})
        car_label = more_itertools.first_true(annotation_specs["labels"], pred=lambda e: get_english_message(e["label_name"]) == "car")
        if car_label is None:
            return False

        if car_label["annotation_type"] != "bounding_box":
            return False

        truncation_attribute = more_itertools.first_true(annotation_specs["additionals"], pred=lambda e: get_english_message(e["name"]) == "truncation")
        if truncation_attribute is None:
            return False

        if truncation_attribute["type"] != "flag":
            return False

        if truncation_attribute["additional_data_definition_id"] not in car_label["additional_data_definitions"]:
            return False

        return True

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

    def test_scenario(self, target_task):
        """
        シナリオテスト。すべてのannotation系コマンドを実行する。
        前提条件：矩形の"car"ラベルに"truncation"チェックボックスが存在すること
        """
        assert self._validate_annotation_specs_for_scenario_test(), (
            "アノテーション仕様がシナリオテストを実行できる状態でありません。矩形の'car'ラベルを追加して、その下に'truncation'チェックボックスを追加してください。"
        )  # noqa: E501

        task_id = target_task["task_id"]
        # インポート用のアノテーションを生成して、アノテーションをインポートする
        self._execute_import(task_id, input_data_id)

        # すぐに`api.get_annotation_list`を実行すると、インポートしたアノテーションが含まれないので、数秒待つ
        time.sleep(2)

        # copyコマンドのテスト
        self._execute_copy(task_id, input_data_id)

        # 属性とプロパティの変更
        self._execute_change_properties_and_attributes(task_id, input_data_id)

        # アノテーションのダンプ、削除、リストア
        self._execute_dump_delete_restore(task_id, input_data_id)

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

    def write_simple_annotation(self, task_id: str, input_data_id: str, annotation_dir: Path) -> None:
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
                '{"label":"car"}',
                "--attributes",
                '{"truncation": false}',
                "--yes",
            ]
        )

        # 属性を確認するためにSimpleアノテーションを取得する
        simple_annotation, _ = service.api.get_annotation(project_id, task_id, input_data_id)
        detail = simple_annotation["details"][0]
        assert detail["attributes"]["truncation"] is False

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
        assert detail["is_protected"] is True

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
            time.sleep(2)

            # アノテーションの削除
            main(["annotation", "delete", "--project_id", project_id, "--task_id", task_id, "--yes"])

            # print("すぐに`annotation delete`を実行すると、'ALREADY UPDATED'で失敗する可能性があるので、数秒待つ")
            time.sleep(2)
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
            # print("すぐに`annotation delete`を実行すると、'ALREADY UPDATED'で失敗する可能性があるので、数秒待つ")
            time.sleep(2)
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
        assert detail["label"] == "car"
        assert detail["attributes"]["truncation"]

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

    def test_download(self):
        main(
            [
                "annotation",
                "download",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "annotation-download.zip"),
            ]
        )

    def test_list(self):
        """
        list系のコマンドのテスト
        """
        main(
            [
                "annotation",
                "list",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "annotation-list.csv"),
            ]
        )

    def test_list_count(self):
        main(
            [
                "annotation",
                "list_count",
                "--project_id",
                project_id,
                "--output",
                str(out_dir / "annotation-list_count.csv"),
            ]
        )
