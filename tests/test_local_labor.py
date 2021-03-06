from pathlib import Path

import pandas

from annofabcli.labor.list_worktime_by_user import LaborAvailability, ListWorktimeByUserMain

out_path = Path("./tests/out/labor")
data_path = Path("./tests/data/labor")
(out_path / "labor").mkdir(exist_ok=True, parents=True)


class TestListWorktimeByUser:
    def test_get_first_and_last_date(self):
        first_date, last_date = ListWorktimeByUserMain.get_first_and_last_date("2019-01")
        assert first_date == "2019-01-01"
        assert last_date == "2019-01-31"

    def test_get_first_and_last_date2(self):
        first_date, last_date = ListWorktimeByUserMain.get_first_and_last_date("2019-02")
        assert first_date == "2019-02-01"
        assert last_date == "2019-02-28"

    def test_get_start_and_end_date_from_month(self):
        start_date, end_date = ListWorktimeByUserMain.get_start_and_end_date_from_month("2019-01", "2019-02")
        assert start_date == "2019-01-01"
        assert end_date == "2019-02-28"

    def test_get_start_and_end_date_from_month2(self):
        start_date, end_date = ListWorktimeByUserMain.get_start_and_end_date_from_month("2019-12", "2020-01")
        assert start_date == "2019-12-01"
        assert end_date == "2020-01-31"

    def test_create_worktime_df_per_date_user(self):
        worktime_df = pandas.read_csv(data_path / "detail-worktime.csv")
        user_df = pandas.read_csv(data_path / "user.csv")
        df = ListWorktimeByUserMain.create_worktime_df_per_date_user(worktime_df, user_df=user_df)
        df.to_csv(out_path / "worktime-per-date-user.csv")

        labor_availability_list_dict = {
            "alice": [
                LaborAvailability(
                    date="2020-04-01", account_id="", user_id="alice", username="Alice", availability_hour=3
                ),
                LaborAvailability(
                    date="2020-04-02", account_id="", user_id="alice", username="Alice", availability_hour=2
                ),
            ],
            "bob": [
                LaborAvailability(
                    date="2020-04-01", account_id="", user_id="bob", username="Bob", availability_hour=3.5
                ),
                LaborAvailability(
                    date="2020-04-02", account_id="", user_id="bob", username="Bob", availability_hour=2.5
                ),
            ],
        }
        df2 = ListWorktimeByUserMain.create_worktime_df_per_date_user(
            worktime_df, user_df=user_df, labor_availability_list_dict=labor_availability_list_dict
        )
        df2.to_csv(out_path / "worktime-per-date-user2.csv")

        # worktime_dfが０件の時
        df3 = ListWorktimeByUserMain.create_worktime_df_per_date_user(
            worktime_df=pandas.DataFrame(columns=["date", "user_id", "worktime_plan_hour", "worktime_result_hour"]),
            user_df=user_df,
            labor_availability_list_dict=labor_availability_list_dict,
        )
        df3.to_csv(out_path / "worktime-per-date-user3.csv")

        # worktime_dfとlabor_availability_list_dictの両方が０件の時
        df4 = ListWorktimeByUserMain.create_worktime_df_per_date_user(
            worktime_df=pandas.DataFrame(columns=["date", "user_id", "worktime_plan_hour", "worktime_result_hour"]),
            user_df=user_df,
            labor_availability_list_dict=None,
        )
        df4.to_csv(out_path / "worktime-per-date-user4.csv")

    def test_create_worktime_df_per_user(self):
        worktime_df_per_date_user = pandas.read_csv(data_path / "worktime-per-date-user.csv")
        user_df = pandas.read_csv(data_path / "user.csv")
        df = ListWorktimeByUserMain.create_worktime_df_per_user(worktime_df_per_date_user, user_df)
        df.to_csv(out_path / "worktime-per-user.csv")
