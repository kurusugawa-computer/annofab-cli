from __future__ import annotations

import pytest

from annofabcli.annotation_specs.color import hex_to_rgb, rgb_to_hex


class TestHexToRgb:
    def test_hex_to_rgb(self) -> None:
        actual = hex_to_rgb("#00CCFF")
        assert actual == {"red": 0, "green": 204, "blue": 255}

    def test_hex_to_rgb__accepts_lowercase(self) -> None:
        actual = hex_to_rgb("#00ccff")
        assert actual == {"red": 0, "green": 204, "blue": 255}

    def test_hex_to_rgb__invalid(self) -> None:
        with pytest.raises(ValueError):
            hex_to_rgb("00CCFF")


class TestRgbToHex:
    def test_rgb_to_hex(self) -> None:
        actual = rgb_to_hex({"red": 0, "green": 204, "blue": 255})
        assert actual == "#00CCFF"

    def test_rgb_to_hex__zero_padding(self) -> None:
        actual = rgb_to_hex({"red": 0, "green": 1, "blue": 15})
        assert actual == "#00010F"

    def test_rgb_to_hex__invalid(self) -> None:
        with pytest.raises(ValueError):
            rgb_to_hex({"red": -1, "green": 204, "blue": 255})
