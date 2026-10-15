Metadata = dict[str, str]
"""入力データのメタデータ。値は文字列。"""


def validate_metadata(metadata: Metadata) -> bool:
    """
    メタデータの値を検証します。
    * メタデータの値がstr型であること
    """
    return all(isinstance(value, str) for value in metadata.values())
