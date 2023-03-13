from pathlib import Path

import pandas

from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)

output_dir = Path("./tests/out/statistics/visualization/dataframe")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestWholeProductivityPerCompletedDate:
    main_obj: WholeProductivityPerCompletedDate

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        df_worktime = pandas.read_csv(str(data_dir / "ユーザ_日付list-作業時間.csv"))

        cls.main_obj = WholeProductivityPerCompletedDate.from_df(df_task, df_worktime)

    def test_from_df__df_worktime引数が空でもインスタンスを生成できることを確認する(self):
        # 完了タスクが１つもない状態で試す
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        df_worktime = pandas.DataFrame()
        obj = WholeProductivityPerCompletedDate.from_df(df_task, df_worktime)
        df_actual = obj.df

        # 日毎の完了したタスク数が一致していることの確認
        assert df_actual["task_count"].sum() == 3
        assert df_actual[df_actual["date"] == "2019-11-14"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-15"].iloc[0]["task_count"] == 1
        assert df_actual[df_actual["date"] == "2019-11-25"].iloc[0]["task_count"] == 1

        # df_worktimeが空なので作業時間は0であることを確認する
        assert df_actual["actual_worktime_hour"].sum() == 0
        assert df_actual["monitored_worktime_hour"].sum() == 0

    def test_to_csv(self):
        self.main_obj.to_csv(output_dir / "日ごとの生産量と生産性.csv")

    def test_plot(self):
        self.main_obj.plot(output_dir / "折れ線-横軸_日-全体.html")

    def test_plot_cumulatively(self):
        self.main_obj.plot_cumulatively(output_dir / "累積折れ線-横軸_日-全体.html")

    def test_merge(self):
        df1 = pandas.read_csv(str(data_dir / "productivity-per-date.csv"))
        df2 = pandas.read_csv(str(data_dir / "productivity-per-date2.csv"))
        sum_obj = WholeProductivityPerCompletedDate.merge(
            WholeProductivityPerCompletedDate(df1), WholeProductivityPerCompletedDate(df2)
        )
        sum_obj.to_csv(output_dir / "merge-productivity-per-date.csv")


class TestWholeProductivityPerFirstAnnotationStartedDate:
    main_obj: WholeProductivityPerFirstAnnotationStartedDate

    @classmethod
    def setup_class(cls):
        df_task = pandas.read_csv(str(data_dir / "task.csv"))
        cls.main_obj = WholeProductivityPerFirstAnnotationStartedDate.from_df(df_task)

    def test_plot(self):
        self.main_obj.plot(output_dir / "教師付開始日ごとの生産量と生産性.html")

    def test_to_csv(self):
        self.main_obj.to_csv(output_dir / "教師付開始日ごとの生産量と生産性.csv")

    def test_merge(self):
        df1 = pandas.read_csv(str(data_dir / "教師付開始日毎の生産量と生産性.csv"))
        df2 = pandas.read_csv(str(data_dir / "教師付開始日毎の生産量と生産性2.csv"))
        merged_obj = WholeProductivityPerFirstAnnotationStartedDate.merge(
            WholeProductivityPerFirstAnnotationStartedDate(df1), WholeProductivityPerFirstAnnotationStartedDate(df2)
        )
        merged_obj.to_csv(output_dir / "merge-教師付開始日毎の生産量と生産性.csv")
