from typing import Any


def keybind_to_text(keybind: list[dict[str, Any]]) -> str:
    """
    以下の構造を持つkeybindを、人が読める形式に変換します。
    {"alt": False, "code": "Numpad1", "ctrl": False, "shift": False}
    """

    def to_str(one_keybind: dict[str, Any]) -> str:
        keys = []
        if one_keybind.get("ctrl", False):
            keys.append("Ctrl")
        if one_keybind.get("alt", False):
            keys.append("Alt")
        if one_keybind.get("shift", False):
            keys.append("Shift")
        code = one_keybind.get("code", "")
        assert code is not None

        keys.append(f"{code}")
        return "+".join(keys)

    tmp_list = [to_str(elm) for elm in keybind]
    return ",".join(tmp_list)
