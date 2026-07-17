from typing import Any


def validate_keybind_input(keybind: object) -> dict[str, Any]:
    """
    keybindのJSON入力を検証し、CLIで指定できる形式に変換します。
    """

    if not isinstance(keybind, dict):
        raise TypeError("`keybind` にはJSONオブジェクトを指定してください。")

    code = keybind.get("code")
    if not isinstance(code, str) or code == "":
        raise ValueError("`keybind` の `code` には空でない文字列を指定してください。")

    normalized_keybind = {
        "alt": keybind.get("alt", False),
        "code": code,
        "ctrl": keybind.get("ctrl", False),
        "shift": keybind.get("shift", False),
    }
    for key in ["alt", "ctrl", "shift"]:
        if not isinstance(normalized_keybind[key], bool):
            raise TypeError(f"`keybind` の `{key}` には真偽値を指定してください。")

    return normalized_keybind


def keybind_to_api_keybind(keybind: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    CLIで扱う単一keybindを、API向けの配列形式に変換します。
    """
    return [] if keybind is None else [keybind]


def api_keybind_to_keybind(keybind: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    APIのkeybind配列から、CLIで扱う単一keybindを取得します。
    """
    if len(keybind) == 0:
        return None
    return keybind[0]


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
