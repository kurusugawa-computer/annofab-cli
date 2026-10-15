from typing import assert_never

from annofabapi.models import Task, TaskPhase
from annofabapi.utils import get_number_of_rejections


def get_step_for_current_phase(task: Task, number_of_inspections: int) -> int:
    """
    今のフェーズが何回目かを取得する。

    Args:
        task: 対象タスクの情報。phase, phase_stage, histories_by_phase を含む。
        number_of_inspections: 対象プロジェクトの検査フェーズの回数

    Returns:
        現在のフェーズのステップ数
    """
    current_phase = TaskPhase(task["phase"])
    current_phase_stage = task["phase_stage"]
    histories_by_phase = task["histories_by_phase"]

    number_of_rejections_by_acceptance = get_number_of_rejections(histories_by_phase, phase=TaskPhase.ACCEPTANCE)
    match current_phase:
        case TaskPhase.ACCEPTANCE:
            return number_of_rejections_by_acceptance + 1

        case TaskPhase.ANNOTATION:
            number_of_rejections_by_inspection = sum(
                get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage) for phase_stage in range(1, number_of_inspections + 1)
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        case TaskPhase.INSPECTION:
            number_of_rejections_by_inspection = sum(
                get_number_of_rejections(histories_by_phase, phase=TaskPhase.INSPECTION, phase_stage=phase_stage) for phase_stage in range(current_phase_stage, number_of_inspections + 1)
            )
            return number_of_rejections_by_inspection + number_of_rejections_by_acceptance + 1

        case _ as unreachable:
            assert_never(unreachable)
