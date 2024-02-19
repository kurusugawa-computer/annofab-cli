import configparser
from pathlib import Path

import annofabapi
import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.actual_worktime import ActualWorktime
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

output_dir = Path("./tests/out/statistics/visualization/dataframe/worktime_per_date")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestWorktimePerDate:
    def test__from_csv__and__to_csv(self):
        actual = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        actual_first_row = actual.df.iloc[0]
        assert actual_first_row["date"] == "2021-11-01"
        assert actual_first_row["user_id"] == "alice"

        actual.to_csv(output_dir / "test__from_csv__and__to_csv.csv")

    def test__plot_cumulatively(self):
        actual = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        actual.plot_cumulatively(output_dir / "累積折れ線-横軸_日-縦軸_作業時間.html")

    def test__merge(self):
        original_obj = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        merged_obj = WorktimePerDate.merge(original_obj, original_obj)
        df = merged_obj.df
        assert df[(df["date"] == "2021-11-02") & (df["user_id"] == "alice")].iloc[0]["actual_worktime_hour"] == 6
        merged_obj.to_csv(output_dir / "merged-ユーザ_日付list-作業時間.csv")

    def test_empty(self):
        empty = WorktimePerDate.empty()
        assert len(empty.df) == 0

        # 出力されないことの確認
        empty.to_csv(output_dir / "empty.csv")
        empty.plot_cumulatively(output_dir / "empty.html")

        original_object = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        merged_obj = WorktimePerDate.merge(empty, original_object)
        assert len(merged_obj.df) == len(original_object.df)

    def test__mask_user_info(self):
        obj = WorktimePerDate.from_csv(data_dir / "ユーザ_日付list-作業時間.csv")
        masked_obj = obj.mask_user_info(
            to_replace_for_user_id={"alice": "masked_user_id"},
            to_replace_for_username={"Alice": "masked_username"},
            to_replace_for_account_id={"alice": "masked_account_id"},
            to_replace_for_biography={"U.S.": "masked_biography"},
        )

        actual_first_row = masked_obj.df.iloc[0]
        assert actual_first_row["account_id"] == "masked_account_id"
        assert actual_first_row["user_id"] == "masked_user_id"
        assert actual_first_row["username"] == "masked_username"
        assert actual_first_row["biography"] == "masked_biography"


inifile = configparser.ConfigParser()
inifile.read("./pytest.ini", "UTF-8")
annofab_config = dict(inifile.items("annofab"))
project_id = annofab_config["project_id"]


@pytest.mark.access_webapi
class TestWorktimePerDate_webapi:
    service: annofabapi.Resource

    @classmethod
    def setup_class(cls) -> None:
        cls.service = annofabapi.build()

    def test_from_webapi(self):
        actual = WorktimePerDate.from_webapi(self.service, project_id, actual_worktime=ActualWorktime.empty())
        assert len(actual.df) > 0

    def test_from_webapi_with_labor(self):
        df_labor = pandas.read_csv(str(data_dir / "labor-df.csv"))
        df_labor["project_id"] = project_id
        actual = WorktimePerDate.from_webapi(self.service, project_id, actual_worktime=ActualWorktime(df_labor))
        assert len(actual.df) > 0
        actual.to_csv(output_dir / "from_webapi_with_labor.csv")
