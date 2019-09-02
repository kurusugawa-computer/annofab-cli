"""
utils

"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union  # pylint: disable=unused-import

import isodate


def isoduration_to_hour(duration):
    """
    ISO 8601 duration を 時間に変換する
    Args:
        duration (str): ISO 8601 Durationの文字
    Returns:
        変換後の時間。
    """

    return isodate.parse_duration(duration).total_seconds() / 3600


def read_lines(filepath: str) -> List[str]:
    """改行コードを除く"""
    with open(filepath) as f:
        lines = f.readlines()
    return [e.rstrip('\r\n') for e in lines]


def get_english_message(messages: List[Dict[str, str]]) -> str:
    return [m["message"] for m in messages if m["lang"] == "en-US"][0]


def get_japanese_message(messages: List[Dict[str, str]]) -> str:
    return [m["message"] for m in messages if m["lang"] == "ja-JP"][0]
