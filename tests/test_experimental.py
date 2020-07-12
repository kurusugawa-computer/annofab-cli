import os
from pathlib import Path
import configparser
import pandas
import annofabapi

from annofabcli.experimental.dashboard import TaskCount, get_task_count_info_from_task_list, PrintDashBoardMain
from annofabcli.experimental.utils import create_column_list, create_column_list_per_project

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")
out_dir.mkdir(exist_ok=True, parents=True)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")
inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))

project_id = annofab_config["project_id"]
service = annofabapi.build_from_netrc()

class TestListLaborWorktime:
    def test_create_column_list_per_project(self):
        total_df = pandas.read_csv(str(test_dir / "worktime-per-project-date.csv"))
        df = create_column_list_per_project(total_df)
        df.to_csv(out_dir / "column-list-per-project.csv", index=False)

    def test_create_column_list(self):
        total_df = pandas.read_csv(str(test_dir / "worktime-per-project-date.csv"))
        df = create_column_list(total_df)
        df.to_csv(out_dir / "column-list.csv", index=False)


class TestDashboard:
    @classmethod
    def setup_class(cls):
        cls.main_obj = PrintDashBoardMain(service)

    task_list = [
        {"status_for_summary": "complete", "updated_datetime": "2020-04-01T18:36:11.159+09:00"},
        {"status_for_summary": "annotation_not_started", "updated_datetime": "2020-04-02T18:36:11.159+09:00"},
    ]

    def test_get_task_count_info(self):
        actual = get_task_count_info_from_task_list(self.task_list)
        assert actual == TaskCount(complete=1, annotation_not_started=1)

    # def test_create_task_count_info(self):
    #     with open(test_dir / "task.json") as f:
    #         task_list = json.load(f)
    #     actual = self.main_obj.create_dashboard_values(project_id=project_id, date="2020-04-01", task_list=task_list)
    #     print(actual)

    def test_get_task_phase_statistics(self):
        actual = self.main_obj.get_task_phase_statistics(project_id)
        print(actual)
