from typing import Any, cast


def validate_keybind_input(keybind: object) -> list[dict[str, Any]]:
    """
    keybindのJSON入力を検証し、ラベルに設定できる形式に変換します。
    """

    if isinstance(keybind, dict):
        keybind_list = [keybind]
    elif isinstance(keybind, list):
        keybind_list = keybind
    else:
        raise TypeError("`keybind` にはJSONオブジェクトまたはJSONオブジェクトの配列を指定してください。")

    result: list[dict[str, Any]] = []
    for index, one_keybind in enumerate(keybind_list, start=1):
        if not isinstance(one_keybind, dict):
            raise TypeError(f"`keybind` の{index}件目はJSONオブジェクト形式で指定してください。")

        code = one_keybind.get("code")
        if not isinstance(code, str) or code == "":
            raise ValueError(f"`keybind` の{index}件目の `code` には空でない文字列を指定してください。")

        normalized_keybind = {
            "alt": one_keybind.get("alt", False),
            "code": code,
            "ctrl": one_keybind.get("ctrl", False),
            "shift": one_keybind.get("shift", False),
        }
        for key in ["alt", "ctrl", "shift"]:
            if not isinstance(normalized_keybind[key], bool):
                raise TypeError(f"`keybind` の{index}件目の `{key}` には真偽値を指定してください。")

        result.append(cast(dict[str, Any], normalized_keybind))

    return result


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
