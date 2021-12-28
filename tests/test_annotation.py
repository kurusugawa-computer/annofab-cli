import configparser
import os
from pathlib import Path

import annofabapi

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
service = annofabapi.build()


class TestCommandLine:
    def test_change_attributes_of_annotation(self):
        backup_dir = str(out_dir / "backup-annotation")
        main(
            [
                "annotation",
                "change_attributes",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--backup",
                backup_dir,
                "--annotation_query",
                '{"label_name_en": "car"}',
                "--attributes",
                '[{"additional_data_definition_name_en": "occluded", "flag": false}]',
                "--yes",
            ]
        )

    def test_copy_annotation(self):
        main(
            [
                "annotation",
                "copy",
                "--project_id",
                project_id,
                "--input",
                f"{task_id}:{task_id}",
                "--yes",
                "--overwrite",
                "--force",
            ]
        )

    def test_dump_annotation(self):
        output_dir = str(out_dir / "dump-annotation")
        main(
            [
                "annotation",
                "dump",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                output_dir,
                "--yes",
            ]
        )

    def test_import(self):
        main(
            [
                "annotation",
                "import",
                "--project_id",
                project_id,
                "--annotation",
                str(data_dir / "imported-annotation.zip"),
                "--task_id",
                task_id,
                "--overwrite",
                "--yes",
            ]
        )

    def test_list(self):
        main(
            [
                "annotation",
                "list",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--output",
                str(out_dir / "annotation_count.csv"),
            ]
        )

    def test_list_count(self):
        main(
            [
                "annotation",
                "list_count",
                "--project_id",
                project_id,
                "--annotation_query",
                '{"label_name_en": "car"}',
                "--task_id",
                task_id,
                "--output",
                str(out_dir / "annotation_count.csv"),
            ]
        )

    def test_delete_and_restore_annotation(self):
        backup_dir = str(out_dir / "backup-annotation")
        main(
            [
                "annotation",
                "delete",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--backup",
                backup_dir,
                "--yes",
            ]
        )

        main(
            [
                "annotation",
                "restore",
                "--project_id",
                project_id,
                "--task_id",
                task_id,
                "--annotation",
                backup_dir,
                "--yes",
            ]
        )
