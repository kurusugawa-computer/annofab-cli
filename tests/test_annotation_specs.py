import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

data_dir = Path("./tests/data/annotation_specs")
out_dir = Path("./tests/out/annotation_specs")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
task_id = annofab_config["task_id"]
service = annofabapi.build()


class TestCommandLine:
    command_name = "annotation_specs"

    def test__export_annotation_specs(self):
        out_file = str(out_dir / "annotation_specs__export.json")
        main(
            [
                self.command_name,
                "export",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

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

    def test__list_label__with_csv_format(self):
        out_file = str(out_dir / "list_label.csv")
        main(
            [
                self.command_name,
                "list_label",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test__list_attribute__with_csv_format(self):
        out_file = str(out_dir / "list_attribute.csv")
        main(
            [
                self.command_name,
                "list_attribute",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test__list_choice__with_csv_format(self):
        out_file = str(out_dir / "list_choice.csv")
        main(
            [
                self.command_name,
                "list_choice",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )
