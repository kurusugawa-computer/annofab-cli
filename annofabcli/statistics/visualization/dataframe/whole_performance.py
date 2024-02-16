# pylint: disable=too-many-lines
"""
各ユーザの合計の生産性と品質
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas
from annofabapi.models import TaskPhase

from annofabcli.statistics.visualization.dataframe.task import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


class WholePerformance:
    """
    全体の生産性と品質の情報

    Attributes:
        series: 全体の生産性と品質が格納されたpandas.Series
    """

    def __init__(self, series: pandas.Series) -> None:
        self.series = series

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.series) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def from_df_wrapper(
        cls,
        worktime_per_date: WorktimePerDate,
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
    ) -> WholePerformance:
        """
        pandas.DataFrameをラップしたオブジェクトから、インスタンスを生成します。

        Args:
            worktime_per_date: 日ごとの作業時間が記載されたDataFrameを格納したオブジェクト。ユーザー情報の取得や、実際の作業時間（集計タスクに影響しない）の算出に利用します。
            task_worktime_by_phase_user: タスク、フェーズ、ユーザーごとの作業時間や生産量が格納されたオブジェクト。生産量やタスクにかかった作業時間の取得に利用します。

        """
        df_worktime_per_date = worktime_per_date.df.copy()
        df_task_worktime_by_phase_user = task_worktime_by_phase_user.df.copy()

        # 引数で渡されたDataFrame内のユーザー情報を疑似的な値に変更する。
        # そうすれば1人のユーザーが作業したときの生産性情報が算出できる。その結果が全体の生産性情報になる。
        for column in ["account_id", "user_id", "username", "biography"]:
            df_worktime_per_date[column] = "pseudo_value"
            df_task_worktime_by_phase_user[column] = "pseudo_value"

        all_user_performance = UserPerformance.from_df_wrapper(
            worktime_per_date=WorktimePerDate(df_worktime_per_date),
            task_worktime_by_phase_user=TaskWorktimeByPhaseUser(df_task_worktime_by_phase_user),
        )

        df_all = all_user_performance.df
        assert len(df_all) == 1

        # 作業している人数をカウントする（実際の計測作業時間でカウントする）
        df_worktime2 = worktime_per_date.df.groupby("account_id")[
            [
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
            ]
        ].sum()
        for phase in TaskPhase:
            df_all[("working_user_count", phase.value)] = (
                df_worktime2[f"monitored_{phase.value}_worktime_hour"] > 0
            ).sum()

        df_all = df_all.drop(
            [("account_id", ""), ("user_id", ""), ("username", ""), ("biography", "")], axis=1, errors="ignore"
        )
        return cls(df_all.iloc[0])

    @classmethod
    def empty(cls) -> WholePerformance:
        """空のデータフレームを持つインスタンスを生成します。"""
        return cls.from_user_performance(UserPerformance.empty())

    @classmethod
    def from_csv(cls, csv_file: Path) -> WholePerformance:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file), header=None, index_col=[0, 1])
        # 3列目を値としたpandas.Series を取得する。
        series = df[2]
        return cls(series)

    def to_csv(self, output_file: Path) -> None:
        """
        全体の生産性と品質が格納されたCSVを出力します。

        """
        if not self._validate_df_for_output(output_file):
            return

        # 列の順番を整える
        phase_list = UserPerformance.get_phase_list(self.series.index)
        indexes = [
            *UserPerformance.get_productivity_columns(phase_list),
            ("working_user_count", TaskPhase.ANNOTATION.value),
            ("working_user_count", TaskPhase.INSPECTION.value),
            ("working_user_count", TaskPhase.ACCEPTANCE.value),
        ]

        series = self.series[indexes]

        output_file.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{str(output_file)} を出力します。")
        series.to_csv(str(output_file), sep=",", encoding="utf_8_sig", header=False)
