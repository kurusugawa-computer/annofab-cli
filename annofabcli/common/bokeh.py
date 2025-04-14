from __future__ import annotations

import json
import math
from typing import Any, Optional

from bokeh.models import LayoutDOM
from bokeh.models.widgets.markups import PreText
from bokeh.plotting import figure


def create_pretext_from_metadata(metadata: dict[str, Any]) -> PreText:
    text_lines = [f"{key} = {json.dumps(value, ensure_ascii=False, indent=2)}" for key, value in metadata.items()]
    text = "\n".join(text_lines)
    return PreText(text=text)


def convert_1d_figure_list_to_2d(figure_list: list[figure], *, ncols: int = 4) -> list[list[Optional[LayoutDOM]]]:
    """
    1次元のfigure_listを、grid layout用に2次元のfigureリストに変換する。
    """
    row_list: list[list[Optional[LayoutDOM]]] = []

    for i in range(math.ceil(len(figure_list) / ncols)):
        start = i * ncols
        end = (i + 1) * ncols
        row: list[Optional[LayoutDOM]] = []
        row.extend(figure_list[start:end])
        if len(row) < ncols:
            row.extend([None] * (ncols - len(row)))
        row_list.append(row)

    return row_list
