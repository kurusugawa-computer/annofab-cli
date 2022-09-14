import abc
from enum import Enum
from pathlib import Path

import pandas


class WorktimeColumn(Enum):
    """作業時間を表す列"""

    ACTUAL_WORKTIME_HOUR = "actual_worktime_hour"
    """実績作業時間"""
    MONITORED_WORKTIME_HOUR = "monitored_worktime_hour"
    """計測作業時間"""


class VisualizationDataFrame(abc.ABC):
    """
    `visualize_statistics.py`が出力するCSVを表すクラスです。

    Args:
        df: CSVに対応するpandas.DataFrame

    """

    def __init__(self, df: pandas.DataFrame) -> None:
        self.df = df

    @classmethod
    @abc.abstractmethod
    def from_csv(cls, csv_file: Path) -> "VisualizationDataFrame":
        """
        CSVからインスタンスを生成します。

        Args:
            csv_file: CSVのパス

        Returns:
            インスタンス
        """

    @abc.abstractmethod
    def to_csv(self, output_file: Path) -> None:
        """
        CSVを出力します。

        Args:
            output_file: 出力先のパス
        """

    @classmethod
    @abc.abstractmethod
    def empty(cls) -> "VisualizationDataFrame":
        """
        空であるDataFrameを持つインスタンスを生成します。

        Returns:
            空であるDataFrameを持つインスタンス
        """

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0
