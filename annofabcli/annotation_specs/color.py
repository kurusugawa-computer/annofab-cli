from __future__ import annotations

import re
from typing import TypedDict


class RgbColor(TypedDict):
    """
    Annofab API で利用する RGB 色です。
    """

    red: int
    green: int
    blue: int


def hex_to_rgb(color_code: str) -> RgbColor:
    """
    16進数カラーコードを Annofab API 向けの RGB 辞書へ変換する。

    Args:
        color_code: ``#RRGGBB`` 形式のカラーコード

    Returns:
        Annofab API 向けの RGB 辞書

    Raises:
        ValueError: 形式が ``#RRGGBB`` でない場合
    """
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", color_code) is None:
        raise ValueError("`--color` には `#RRGGBB` 形式の16進数カラーコードを指定してください。")

    return {
        "red": int(color_code[1:3], 16),
        "green": int(color_code[3:5], 16),
        "blue": int(color_code[5:7], 16),
    }


def rgb_to_hex(color: RgbColor) -> str:
    """
    Annofab API 向けの RGB 辞書を16進数カラーコードへ変換する。

    Args:
        color: Annofab API 向けの RGB 辞書

    Returns:
        ``#RRGGBB`` 形式のカラーコード

    Raises:
        ValueError: RGB値が0から255の範囲外の場合
    """
    red = color["red"]
    green = color["green"]
    blue = color["blue"]
    if not (0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255):
        raise ValueError(f"RGB values must be in the range 0-255 :: {red=}, {green=}, {blue=}")

    return f"#{red:02X}{green:02X}{blue:02X}"
