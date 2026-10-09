"""タスク数の集計結果の出力処理。"""

from pathlib import Path

import pandas

from annofabcli.common.enums import OutputFormat
from annofabcli.common.utils import print_according_to_format, print_csv


def print_task_count_summary(df: pandas.DataFrame, *, format: OutputFormat, output: str | Path | None = None) -> None:  # noqa: A002
    """集計結果を指定した形式で出力する。

    Args:
        df: 集計キーと集計値を列に持つ集計結果。
        format: 出力形式。
        output: 出力先。Noneなら標準出力に出力する。

    Returns:
        None
    """
    if format == OutputFormat.CSV:
        print_csv(df, output=output)
    else:
        # JSONでは欠損値をnullとして出力する。
        records = df.astype(object).where(df.notna(), None).to_dict(orient="records")
        print_according_to_format(records, format=format, output=output)
