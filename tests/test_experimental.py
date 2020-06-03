import os
from pathlib import Path

import pandas

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
