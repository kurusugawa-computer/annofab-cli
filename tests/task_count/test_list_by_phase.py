import configparser
from pathlib import Path

import annofabapi
import pytest

from annofabcli.__main__ import main

# webapiにアクセスするテストモジュール
pytestmark = pytest.mark.access_webapi

out_dir = Path("./tests/out/task_count")
out_dir.mkdir(exist_ok=True, parents=True)

inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build()


class TestCommandLine:
    command_name = "task_count"

    def test_list_by_phase(self):
        out_file = str(out_dir / "list_by_phase.csv")
        main(
            [
                self.command_name,
                "list_by_phase",
                "--project_id",
                project_id,
                "--output",
                out_file,
            ]
        )

    def test_list_by_phase_with_input_data_unit(self):
        out_file = str(out_dir / "list_by_phase_input_data.csv")
        main(
            [
                self.command_name,
                "list_by_phase",
                "--project_id",
                project_id,
                "--unit",
                "input_data",
                "--output",
                out_file,
            ]
        )

    def test_list_by_phase_with_video_duration_hour_unit(self):
        out_file = str(out_dir / "list_by_phase_video_duration_hour.csv")
        main(
            [
                self.command_name,
                "list_by_phase",
                "--project_id",
                project_id,
                "--unit",
                "video_duration_hour",
                "--output",
                out_file,
            ]
        )

    def test_list_by_phase_with_video_duration_minute_unit(self):
        out_file = str(out_dir / "list_by_phase_video_duration_minute.csv")
        main(
            [
                self.command_name,
                "list_by_phase",
                "--project_id",
                project_id,
                "--unit",
                "video_duration_minute",
                "--output",
                out_file,
            ]
        )

    def test_list_by_phase_with_metadata_key(self):
        out_file = str(out_dir / "list_by_phase_with_metadata.csv")
        main(
            [
                self.command_name,
                "list_by_phase",
                "--project_id",
                project_id,
                "--metadata_key",
                "test_key",
                "--output",
                out_file,
            ]
        )
