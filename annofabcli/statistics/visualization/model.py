from dataclasses import dataclass
from enum import Enum
from typing import Any

from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus

from annofabcli.common.type_util import assert_noreturn


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


class TaskCompletionCriteria(Enum):
    """
    タスクの完了の条件
    """

    ACCEPTANCE_COMPLETED = "acceptance_completed"
    """タスクが受入フェーズの完了状態であれば「タスクの完了」とみなす"""
    ACCEPTANCE_REACHED = "acceptance_reached"
    """タスクが受入フェーズに到達したら「タスクの完了」とみなす"""
    INSPECTION_REACHED = "inspection_reached"
    """タスクが検査フェーズに到達したら「タスクの完了」とみなす"""

    def is_task_completed(self, task: dict[str, Any]) -> bool:
        """指定したタスクが、タスクの完了条件に合致するかどうかを判定します。

        Args:
            task: タスク情報。以下のキーを参照します。
                * phase
                * status

        Returns:
            タスクの完了条件に合致する場合はTrue、そうでない場合はFalse
        """
        if self == TaskCompletionCriteria.ACCEPTANCE_COMPLETED:
            return task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value

        elif self == TaskCompletionCriteria.ACCEPTANCE_REACHED:
            return task["phase"] == TaskPhase.ACCEPTANCE.value

        elif self == TaskCompletionCriteria.INSPECTION_REACHED:
            # 受入フェーズも含む理由：検査フェーズに到達したタスクを「完了」とみなすならば、検査フェーズより後段フェーズである受入フェーズも「完了」とみなせるため
            return task["phase"] in {TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value}

        else:
            assert_noreturn(self)
