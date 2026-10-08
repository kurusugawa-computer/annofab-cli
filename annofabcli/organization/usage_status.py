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


def validate_period(from_month: str | None, to_month: str | None, daily_month: str | None) -> None:
    """月別の期間指定と日別の対象月指定の整合性を検証します。

    Args:
        from_month: 月別一覧の開始月。
        to_month: 月別一覧の終了月。
        daily_month: 日別一覧の対象月。

    Returns:
        None。

    Raises:
        AnnofabCliException: 指定が競合するか期間が逆転している場合。
    """
    if daily_month is not None and (from_month is not None or to_month is not None):
        raise AnnofabCliException("--year_monthと--from_month、--to_monthは同時に指定できません。")
    if from_month is not None and to_month is not None and from_month > to_month:
        raise AnnofabCliException("--from_monthは--to_month以前の年月を指定してください。")
