import configparser
import copy
import datetime
import json
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

    def test_scenario_label_color(self):
        """
        label_colorに関するシナリオテスト。
        """
        out_file = out_dir / f"annotation_specs_list_label_color--{datetime.datetime.now().timestamp()!s}.json"
        main(
            [
                self.command_name,
                "list_label_color",
                "--project_id",
                project_id,
                "--format",
                "json",
                "--output",
                str(out_file),
            ]
        )
        with out_file.open() as f:
            old_label_color = json.load(f)

        label_color = copy.deepcopy(old_label_color)
        key = list(label_color.keys())[0]  # noqa: RUF015
        color = label_color[key]
        new_color = (color[0], color[1], (color[2] + 1) % 256)
        label_color[key] = new_color

        main(
            [
                self.command_name,
                "put_label_color",
                "--project_id",
                project_id,
                "--json",
                json.dumps(label_color),
                "--yes",
            ]
        )

        out_file2 = out_dir / f"annotation_specs_list_label_color--{datetime.datetime.now().timestamp()!s}.json"
        main(
            [
                self.command_name,
                "list_label_color",
                "--project_id",
                project_id,
                "--format",
                "json",
                "--output",
                str(out_file2),
            ]
        )

        with out_file2.open() as f:
            new_label_color = json.load(f)

        assert new_label_color[key] == list(new_color)

        # 元の色に戻す
        main(
            [
                self.command_name,
                "put_label_color",
                "--project_id",
                project_id,
                "--json",
                json.dumps(old_label_color),
                "--yes",
            ]
        )

    def test_get_with_label_id_replaced_english_name(self):
        out_file = str(out_dir / "get_with_label_id_replaced_englisth_name.json")
        main(
            [
                self.command_name,
                "get_with_label_id_replaced_english_name",
                "--project_id",
                project_id,
                "--output",
                out_file,
                "--yes",
            ]
        )

    def test_get_with_attribute_id_replaced_english_name(self):
        out_file = str(out_dir / "get_with_attribute_id_replaced_englisth_name.json")
        main(
            [
                self.command_name,
                "get_with_attribute_id_replaced_english_name",
                "--project_id",
                project_id,
                "--output",
                out_file,
                "--yes",
            ]
        )

    def test_get_with_choice_id_replaced_english_name(self):
        out_file = str(out_dir / "get_with_choice_id_replaced_englisth_name.json")
        main(
            [
                self.command_name,
                "get_with_choice_id_replaced_english_name",
                "--project_id",
                project_id,
                "--output",
                out_file,
                "--yes",
            ]
        )
