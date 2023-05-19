import configparser
from pathlib import Path

import annofabapi
import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestWorktimePerDate:
    obj: WorktimePerDate

    @classmethod
    def setup_class(cls):
        df = pandas.read_csv(str(data_dir / "ユーザ_日付list-作業時間.csv"))
        cls.obj = WorktimePerDate(df)

    def test_to_csv(self):
        self.obj.to_csv(output_dir / "ユーザ_日付list-作業時間.csv")

    def test_plot_cumulatively(self):
        self.obj.plot_cumulatively(output_dir / "累積折れ線-横軸_日-縦軸_作業時間.html")

    def test_merge(self):
        merged_obj = WorktimePerDate.merge(self.obj, self.obj)
        df = merged_obj.df
        assert df[(df["date"] == "2021-11-02") & (df["user_id"] == "alice")].iloc[0]["actual_worktime_hour"] == 6
        merged_obj.to_csv(output_dir / "merged-ユーザ_日付list-作業時間.csv")

    def test_empty(self):
        empty = WorktimePerDate.empty()
        assert len(empty.df) == 0

        # 出力されないことの確認
        empty.to_csv(output_dir / "empty.csv")
        empty.plot_cumulatively(output_dir / "empty.html")

        merged_obj = WorktimePerDate.merge(empty, self.obj)
        assert len(merged_obj.df) == len(self.obj.df)


inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))
project_id = annofab_config["project_id"]


@pytest.mark.access_webapi
class TestWorktimePerDate_webapi:
    service: annofabapi.Resource

    @classmethod
    def setup_class(cls):
        cls.service = annofabapi.build()

    def test_from_webapi(self):
        actual = WorktimePerDate.from_webapi(self.service, project_id)
        assert len(actual.df) > 0

    def test_from_webapi_with_labor(self):
        df_labor = pandas.read_csv(str(data_dir / "labor-df.csv"))
        actual = WorktimePerDate.from_webapi(self.service, project_id, df_labor=df_labor)
        assert len(actual.df) > 0
