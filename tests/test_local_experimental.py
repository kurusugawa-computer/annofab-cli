import os
from pathlib import Path

import pandas

from annofabcli.experimental.list_labor_worktime import create_df_with_format_details

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
        df2.to_csv(out_dir / "list_labor_worktime/out_details.csv")

    # def test_create_actual_times_df(self) -> None:
    #     df = self.main_obj.create_actual_times_df(
    #         start_date="2021-03-01", end_date="2021-03-31", project_id_list=["c7ca1609-6117-451e-866e-52626e84b728"]
    #     )
    #     df.to_csv("foo.csv", index=False)
    #     print(df)
    #     pass

    # def test_create_df_with_by_name_total(self):
    #     df = pandas.read_csv(str(data_dir / "intermediate.csv"))
    #     print(df.columns)
    #     df2 = create_df_with_format_by_name_total(df)
    #     print(df2)

    # def test_create_df_with_total(self):
    #     df = pandas.read_csv(str(data_dir / "intermediate2.csv"))
    #     df2 = create_df_with_format_total(df)
    #     df2.to_csv(out_dir / "out.csv")

    # def test_create_df_with_format_column_list(self):
    #     df = pandas.read_csv(str(data_dir / "intermediate2.csv"))
    #     df2 = create_df_with_format_column_list(df)
    #     df2.to_csv(out_dir / "out.csv")
