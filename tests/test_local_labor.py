from annofabcli.labor.list_worktime_by_user import ListWorktimeByUser


class TestListWorktimeByUser:
    def test_get_first_and_last_date(self):
        first_date, last_date = ListWorktimeByUser.get_first_and_last_date("2019-01")
        assert first_date == "2019-01-01"
        assert last_date == "2019-01-31"

    def test_get_first_and_last_date2(self):
        first_date, last_date = ListWorktimeByUser.get_first_and_last_date("2019-02")
        assert first_date == "2019-02-01"
        assert last_date == "2019-02-28"

    def test_get_start_and_end_date_from_month(self):
        start_date, end_date = ListWorktimeByUser.get_start_and_end_date_from_month("2019-01", "2019-02")
        assert start_date == "2019-01-01"
        assert end_date == "2019-02-28"

    def test_get_start_and_end_date_from_month2(self):
        start_date, end_date = ListWorktimeByUser.get_start_and_end_date_from_month("2019-12", "2020-01")
        assert start_date == "2019-12-01"
        assert end_date == "2020-01-31"
