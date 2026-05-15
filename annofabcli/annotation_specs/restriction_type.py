from __future__ import annotations

from collections.abc import Mapping
from typing import Any

RESTRICTION_TYPE_TO_CONDITION_TYPE = {
    "can_input": "CanInput",
    "has_label": "HasLabel",
    "equals": "Equals",
    "not_equals": "NotEquals",
    "matches": "Matches",
    "not_matches": "NotMatches",
    "imply": "Imply",
}
"""CLIの ``--restriction_type`` と Annofab API の ``condition._type`` の対応。"""


def matches_restriction_type(restriction: Mapping[str, Any], restriction_type: str | None) -> bool:
    """
    属性制約が指定した種類に一致するかどうかを返す。

    Args:
        restriction: 判定対象の属性制約
        restriction_type: CLIで指定された属性制約種類。未指定の場合はNone

    Returns:
        条件に一致する場合はTrue
    """
    if restriction_type is None:
        return True
    return restriction["condition"]["_type"] == RESTRICTION_TYPE_TO_CONDITION_TYPE[restriction_type]
