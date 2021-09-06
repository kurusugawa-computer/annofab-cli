import os
from pathlib import Path

import pandas

from annofabcli.experimental.list_labor_worktime import (
    create_df_with_format_total_by_project,
    create_df_with_format_total_by_user,
    create_df_with_format_column_list,
    create_df_with_format_column_list_per_project,
    create_df_with_format_details,
    create_df_with_format_total,
)

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")


class TestListLaborWorktime:
    @classmethod
    def setup_class(cls):
        (out_dir / "list_labor_worktime").mkdir(exist_ok=True, parents=True)

    def test_create_df_with_format_details(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        df2 = create_df_with_format_details(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-details.csv", index=False)

    def test_create_df_with_format_total_by_user(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        print(df.columns)
        df2 = create_df_with_format_total_by_user(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-by_user.csv", index=False)

    def test_create_df_with_total(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        df2 = create_df_with_format_total(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-total.csv", index=False)

    def test_create_df_with_format_column_list(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        df2 = create_df_with_format_column_list(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-column_list.csv")

    def test_create_df_with_format_column_list_per_project(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        df2 = create_df_with_format_column_list_per_project(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-column_list_per_project.csv")

    def test_create_df_with_format_total_by_project(self):
        df = pandas.read_csv(str(data_dir / "list_labor_worktime/intermediate.csv"))
        df2 = create_df_with_format_total_by_project(df)
        df2.to_csv(out_dir / "list_labor_worktime/out-by_project.csv")
