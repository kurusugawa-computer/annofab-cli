import configparser
import os
from pathlib import Path

import annofabapi

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/annotation_specs")
out_dir = Path("./tests/out/annotation_specs")
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
    command_name = "annotation_specs"

    def test_annotation_specs_list_restriction(self):
        out_file = str(out_dir / "annotation_specs_list_restriction.txt")
        main(
            [
                self.command_name,
                "list_attribute_restriction",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_annotation_specs_histories(self):
        out_file = str(out_dir / "anotaton_specs_histories.csv")
        main([self.command_name, "list_history", "--project_id", project_id, "--output", out_file])

    def test_annotation_specs_list_label(self):
        out_file = str(out_dir / "annotation_specs_list_label.json")
        main([self.command_name, "list_label", "--project_id", project_id, "--before", "1", "--output", out_file])

    def test_annotation_specs_list_label_color(self):
        out_file = str(out_dir / "annotation_specs_list_label_color.json")
        main(
            [
                self.command_name,
                "list_label_color",
                "--project_id",
                project_id,
                "--format",
                "json",
                "--output",
                out_file,
            ]
        )

    def test_get_with_label_id_replaced_label_name(self):
        out_file = str(out_dir / "get_with_label_id_replaced_label_name.json")
        main(
            [
                self.command_name,
                "get_with_label_id_replaced_label_name",
                "--project_id",
                project_id,
                "--output",
                out_file,
                "--yes",
            ]
        )
