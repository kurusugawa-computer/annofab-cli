from dataclasses import dataclass
from enum import Enum


class WorktimeColumn(Enum):
    """作業時間を表す列"""

    ACTUAL_WORKTIME_HOUR = "actual_worktime_hour"
    """実績作業時間"""
    MONITORED_WORKTIME_HOUR = "monitored_worktime_hour"
    """計測作業時間"""


@dataclass(frozen=True)
class ProductionVolumeColumn:
    """
    生産量の列情報
    """

    value: str
    """CSVの列名"""
    name: str
    """列の名前。グラフに表示する名前などに使用する"""
