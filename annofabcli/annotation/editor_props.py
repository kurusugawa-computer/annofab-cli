from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool


class EditorPropsForCli(BaseModel):
    """
    `--editor_props` で指定できるエディタ用プロパティ。
    """

    can_delete: StrictBool | None = None
    """アノテーションがエディタ上で削除できるかどうか。"""

    can_edit_data: StrictBool | None = None
    """アノテーションの本体データをエディタ上で編集できるかどうか。"""

    can_edit_additional: StrictBool | None = None
    """アノテーションの付加情報をエディタ上で編集できるかどうか。"""

    model_config = ConfigDict(extra="forbid")


def validate_editor_props_for_cli(editor_props: dict[str, Any] | None) -> dict[str, Any]:
    """
    `--editor_props` の値を検証する。

    Args:
        editor_props: CLIで指定された `editor_props`。

    Returns:
        APIに渡す `editor_props`。

    Raises:
        pydantic.ValidationError: CLIで指定可能な `editor_props` のスキーマに違反している場合。
    """
    if editor_props is None:
        return {}

    return EditorPropsForCli.model_validate(editor_props).model_dump(exclude_none=True)
