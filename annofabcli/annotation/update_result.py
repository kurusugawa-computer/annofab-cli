"""アノテーションの一括変更結果。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnnotationUpdateResult:
    """タスク単位の成功・スキップ・失敗を区別する。"""

    success: bool
    """変更を実施したか。"""
    changed_count: int
    """変更したアノテーション数。"""
    failed: bool = False
    """処理中に例外が発生したか。"""
