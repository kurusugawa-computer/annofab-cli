"""
全体の生産性と品質
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

import numpy
import pandas
from annofabapi.models import TaskPhase

from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user_performance import TaskPhaseString, UserPerformance
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria

logger = logging.getLogger(__name__)


class WholePerformance:
    """
    全体の生産性と品質の情報

    Attributes:
        series: 全体の生産性と品質が格納されたpandas.Series
    """

    STRING_KEYS = {("first_working_date", ""), ("last_working_date", "")}  # noqa: RUF012
    """文字列が格納されているキー"""

    def __init__(
        self,
        series: pandas.Series,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> None:
        self.series = series
        self.task_completion_criteria = task_completion_criteria
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.series) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @staticmethod
    def _create_all_user_performance(
        worktime_per_date: WorktimePerDate,
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
        task_completion_criteria: TaskCompletionCriteria,
    ) -> UserPerformance:
        """
        1人が作業した場合のパフォーマンス情報を生成します。
        ユーザー情報である以下の列には、`pseudo_value`が設定されています。
        * account_id
        * user_id
        * username
        * biography
        """
        df_worktime_per_date = worktime_per_date.df.copy()
        df_task_worktime_by_phase_user = task_worktime_by_phase_user.df.copy()

        PSEUDO_VALUE = "pseudo_value"  # noqa: N806
        user_info_columns = ["account_id", "user_id", "username", "biography"]
        # 引数で渡されたDataFrame内のユーザー情報を疑似的な値に変更する。
        # そうすれば1人のユーザーが作業したときの生産性情報が算出できる。その結果が全体の生産性情報になる。
        for column in user_info_columns:
            df_worktime_per_date[column] = "pseudo_value"
            df_task_worktime_by_phase_user[column] = "pseudo_value"

        unique_keys_for_worktime = ["date"]
        addable_columns_for_worktime = list(set(df_worktime_per_date.columns) - set(user_info_columns) - set(unique_keys_for_worktime))
        df_worktime_per_date = df_worktime_per_date.groupby(unique_keys_for_worktime)[addable_columns_for_worktime].sum()
        df_worktime_per_date[user_info_columns] = PSEUDO_VALUE
        df_worktime_per_date = df_worktime_per_date.reset_index()

        # `status`はあとで結合するため、`df_task`を作る
        df_task = df_task_worktime_by_phase_user[["project_id", "task_id", "status"]].drop_duplicates()

        unique_keys_for_worktime = ["project_id", "task_id", "phase", "phase_stage"]
        addable_columns_for_task = list(set(df_task_worktime_by_phase_user.columns) - set(user_info_columns) - set(unique_keys_for_worktime) - {"status"})
        df_task_worktime_by_phase_user = df_task_worktime_by_phase_user.groupby(unique_keys_for_worktime)[addable_columns_for_task].sum()
        df_task_worktime_by_phase_user[user_info_columns] = PSEUDO_VALUE
        df_task_worktime_by_phase_user = df_task_worktime_by_phase_user.reset_index()
        # status情報を結合する
        df_task_worktime_by_phase_user = df_task_worktime_by_phase_user.merge(df_task, on=["project_id", "task_id"])

        return UserPerformance.from_df_wrapper(
            worktime_per_date=WorktimePerDate(df_worktime_per_date),
            task_worktime_by_phase_user=TaskWorktimeByPhaseUser(df_task_worktime_by_phase_user, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list),
            task_completion_criteria=task_completion_criteria,
        )

    @classmethod
    def from_df_wrapper(
        cls,
        worktime_per_date: WorktimePerDate,
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
        task_completion_criteria: TaskCompletionCriteria,
    ) -> WholePerformance:
        """
        pandas.DataFrameをラップしたオブジェクトから、インスタンスを生成します。

        Args:
            worktime_per_date: 日ごとの作業時間が記載されたDataFrameを格納したオブジェクト。ユーザー情報の取得や、実際の作業時間（集計タスクに影響しない）の算出に利用します。
            task_worktime_by_phase_user: タスク、フェーズ、ユーザーごとの作業時間や生産量が格納されたオブジェクト。生産量やタスクにかかった作業時間の取得に利用します。

        """
        # 1人が作業した場合のパフォーマンス情報を生成する
        all_user_performance = cls._create_all_user_performance(worktime_per_date, task_worktime_by_phase_user, task_completion_criteria)

        df_all = all_user_performance.df
        # タスクは存在するが合計の作業時間が0時間の場合
        if len(df_all) == 0:
            return WholePerformance.empty(task_completion_criteria)

        # 1人が作業した場合のパフォーマンス情報を生成しているので、lengthは1のはず
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
            df_all[("working_user_count", phase.value)] = (df_worktime2[f"monitored_{phase.value}_worktime_hour"] > 0).sum()

        df_all = df_all.drop([("account_id", ""), ("user_id", ""), ("username", ""), ("biography", "")], axis=1, errors="ignore")
        return cls(df_all.iloc[0], task_completion_criteria, custom_production_volume_list=task_worktime_by_phase_user.custom_production_volume_list)

    @classmethod
    def empty(cls, task_completion_criteria: TaskCompletionCriteria, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> WholePerformance:
        """空のデータフレームを持つインスタンスを生成します。"""

        production_volume_columns = ["input_data_count", "annotation_count"]
        if custom_production_volume_list is not None:
            production_volume_columns.extend([e.value for e in custom_production_volume_list])

        phase = TaskPhase.ANNOTATION.value

        worktime_columns = [
            ("real_monitored_worktime_hour", "sum"),
            # 常に全フェーズを出力する
            ("real_monitored_worktime_hour", "annotation"),
            ("real_monitored_worktime_hour", "inspection"),
            ("real_monitored_worktime_hour", "acceptance"),
            ("real_actual_worktime_hour", "sum"),
            ("monitored_worktime_hour", "sum"),
            ("monitored_worktime_hour", phase),
            ("actual_worktime_hour", "sum"),
            ("actual_worktime_hour", phase),
        ]

        count_columns = [
            ("task_count", phase),
            *[(col, phase) for col in production_volume_columns],
            ("pointed_out_inspection_comment_count", phase),
            ("rejected_count", phase),
            # 常に全フェーズを出力する
            ("working_user_count", "annotation"),
            ("working_user_count", "inspection"),
            ("working_user_count", "acceptance"),
        ]

        ratio_columns = [
            ("monitored_worktime_ratio", phase),
            ("real_monitored_worktime_hour/real_actual_worktime_hour", "sum"),
            *[(f"monitored_worktime_hour/{col}", phase) for col in production_volume_columns],
            *[(f"actual_worktime_hour/{col}", phase) for col in production_volume_columns],
            *[(f"pointed_out_inspection_comment_count/{col}", phase) for col in production_volume_columns],
            ("rejected_count/task_count", phase),
        ]

        stdev_columns = [
            *[(f"stdev__monitored_worktime_hour/{col}", phase) for col in production_volume_columns],
            *[(f"stdev__actual_worktime_hour/{col}", phase) for col in production_volume_columns],
        ]

        date_columns = [
            ("first_working_date", ""),
            ("last_working_date", ""),
            ("working_days", ""),
        ]

        data: dict[tuple[str, str], float] = dict.fromkeys(worktime_columns + count_columns, 0)
        data.update(dict.fromkeys(ratio_columns + stdev_columns + date_columns, numpy.nan))

        return cls(pandas.Series(data), task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_csv(
        cls,
        csv_file: Path,
        task_completion_criteria: TaskCompletionCriteria,
        *,
        custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None,
    ) -> WholePerformance:
        """CSVファイルからインスタンスを生成します。"""
        df = pandas.read_csv(str(csv_file), header=None, index_col=[0, 1])
        # 3列目を値としたpandas.Series を取得する。
        series = df[2]

        data = {}
        # CSVファイル読み込み直後では、数値も文字列として格納されているので、文字列情報以外は数値に変換する
        for key, value in series.items():
            # `first_working_date`など2列目が空欄の場合は、key[1]がnumpy.nanになるため、keyを変換する
            if isinstance(key[1], float) and numpy.isnan(key[1]):
                key2 = (key[0], "")
            else:
                key2 = key

            if key2 in cls.STRING_KEYS:
                value2 = value
            else:
                value2 = float(value)

            data[key2] = value2

        return cls(pandas.Series(data), task_completion_criteria, custom_production_volume_list=custom_production_volume_list)

    def to_csv(self, output_file: Path) -> None:
        """
        全体の生産性と品質が格納されたCSVを出力します。

        """
        if not self._validate_df_for_output(output_file):
            return

        # 列の順番を整える
        phase_list = UserPerformance.get_phase_list(self.series.index)
        production_volume_columns = ["input_data_count", "annotation_count", *[e.value for e in self.custom_production_volume_list]]
        indexes = self.get_series_index(phase_list, production_volume_columns=production_volume_columns)
        series = self.series[indexes]

        output_file.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{output_file!s} を出力します。")
        series.to_csv(str(output_file), sep=",", encoding="utf_8_sig", header=False)

    @staticmethod
    def get_series_index(phase_list: Sequence[TaskPhaseString], production_volume_columns: list[str]) -> list[tuple[str, str]]:
        """
        格納しているpandas.Seriesのindexを取得する。
        """
        # 列の順番を整える
        return [
            ("first_working_date", ""),
            ("last_working_date", ""),
            ("working_days", ""),
            *UserPerformance.get_productivity_columns(phase_list, production_volume_columns),
            ("working_user_count", TaskPhase.ANNOTATION.value),
            ("working_user_count", TaskPhase.INSPECTION.value),
            ("working_user_count", TaskPhase.ACCEPTANCE.value),
        ]
