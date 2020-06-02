import os
from pathlib import Path

import pandas

from annofabcli.experimental.summarize_task_count_by_task_id import create_task_count_summary_df, get_task_id_prefix
from annofabcli.experimental.utils import create_column_list, create_column_list_per_project

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")
out_dir.mkdir(exist_ok=True, parents=True)


class TestListLaborWorktime:
    def test_create_column_list_per_project(self):
        total_df = pandas.read_csv(str(test_dir / "worktime-per-project-date.csv"))
        df = create_column_list_per_project(total_df)
        df.to_csv(out_dir / "column-list-per-project.csv", index=False)

    def test_create_column_list(self):
        total_df = pandas.read_csv(str(test_dir / "worktime-per-project-date.csv"))
        df = create_column_list(total_df)
        df.to_csv(out_dir / "column-list.csv", index=False)


class TestSummarizeTaskCountByTaskId:
    task_list = [
        {"task_id": "A_A_01", "status": "complete"},
        {"task_id": "A_A_02", "status": "not_started"},
        {"task_id": "A_B_02", "status": "on_hold"},
        {"task_id": "abc", "status": "break"},
    ]

    def test_get_task_id_prefix(self):
        assert get_task_id_prefix("A_A_01") == "A_A"
        assert get_task_id_prefix("abc") == "unknown"

    def test_create_task_count_summary_df(self):
        df = create_task_count_summary_df(self.task_list)
        print(df.columns)
        print(df)
