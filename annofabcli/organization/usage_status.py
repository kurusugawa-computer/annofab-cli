"""組織の利用状況コマンドで使用する年月の検証。"""

import argparse
import re

from annofabcli.common.exceptions import AnnofabCliException


def year_month(value: str) -> str:
    """YYYY-MM形式の年月を検証します。

    Args:
        value: コマンドラインで指定された年月。

    Returns:
        検証済みの年月。

    Raises:
        argparse.ArgumentTypeError: 年月の形式が不正な場合。
    """
    if re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value) is None or value.startswith("0000"):
        raise argparse.ArgumentTypeError("年月はYYYY-MM形式で指定してください。")
    return value


def validate_period(start_month: str | None, end_month: str | None, daily_month: str | None) -> None:
    """月別の期間指定と日別の対象月指定の整合性を検証します。

    Args:
        start_month: 月別一覧の開始月。
        end_month: 月別一覧の終了月。
        daily_month: 日別一覧の対象月。

    Returns:
        None。

    Raises:
        AnnofabCliException: 指定が競合するか期間が逆転している場合。
    """
    if daily_month is not None and (start_month is not None or end_month is not None):
        raise AnnofabCliException("--monthと--start_month、--end_monthは同時に指定できません。")
    if start_month is not None and end_month is not None and start_month > end_month:
        raise AnnofabCliException("--start_monthは--end_month以前の年月を指定してください。")
