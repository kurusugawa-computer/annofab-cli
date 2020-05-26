import configparser
import json
import os
from pathlib import Path

import annofabapi

from annofabcli.statistics.csv import Csv
from annofabcli.statistics.database import Database
from annofabcli.statistics.table import Table

out_path = Path("./tests/out")
data_path = Path("./tests/data/statistics")
(out_path / "statistics").mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build_from_netrc()

csv_obj = Csv(str(out_path), project_id)
database_obj = Database(service, project_id, chekpoint_dir=str(data_path), query=None,)
table_obj = Table(database_obj)


class TestDatabase:
    def test_read_annotation_summary(self):
        with open(data_path / "task.json") as f:
            task_list = json.load(f)
        result = database_obj.read_annotation_summary(task_list, table_obj._create_annotation_summary)
        assert "sample_0" in result
        assert "sample_1" in result
