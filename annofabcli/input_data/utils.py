from __future__ import annotations

from typing import Any


def remove_unnecessary_keys_from_input_data(input_data: dict[str, Any]) -> None:
    """
    入力データから不要なキーを取り除きます。
    システム内部用のプロパティなど、annofab-cliを使う上で不要な情報を削除します。

    Args:
        input_data: (IN/OUT) 入力データ情報。引数が変更されます。
    """
    unnecessary_keys = [
        "url",  # システム内部用のプロパティ
        "original_input_data_path",  # システム内部用のプロパティ
        "etag",  # annofab-cliで見ることはない
    ]
    for key in unnecessary_keys:
        input_data.pop(key, None)


def validate_metadata(metadata: dict[str, str]) -> bool:
    """入力データのメタデータの値が文字列であることを検証する。

    Args:
        metadata: 検証するメタデータ。

    Returns:
        すべての値が文字列の場合はTrue。
    """
    return all(isinstance(value, str) for value in metadata.values())
