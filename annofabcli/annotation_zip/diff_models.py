"""アノテーションZIPの差分モデル。"""

from pydantic import BaseModel, Field, JsonValue, computed_field


class AnnotationKey(BaseModel):
    """パスとアノテーションIDから決まる比較キー。"""

    task_id: str
    """JSONの親ディレクトリ名。"""
    input_data_id: str
    """JSONファイルの拡張子を除いた名前。"""
    annotation_id: str
    """アノテーションID。"""


class ValueChange(BaseModel):
    """変更前後の値。"""

    left: JsonValue
    """比較元の値。"""
    right: JsonValue
    """比較先の値。"""


class ChangedAnnotation(AnnotationKey):
    """既存アノテーションの差分。"""

    label_changed: bool = False
    """ラベルが変更されたか。"""
    data_changed: bool = False
    """座標・種類・外部ファイルの内容が変更されたか。"""
    attributes_changed: bool = False
    """属性が変更されたか。"""
    external_file_changed: bool = False
    """外部ファイルの内容が変更されたか。"""
    added_attribute_keys: list[str] = Field(default_factory=list)
    """追加された属性キー。"""
    removed_attribute_keys: list[str] = Field(default_factory=list)
    """削除された属性キー。"""
    changed_attribute_keys: list[str] = Field(default_factory=list)
    """値が変更された属性キー。"""
    external_file: dict[str, JsonValue] | None = None
    """外部ファイルの差分件数。点インデックスは含めない。"""
    changes: dict[str, ValueChange] = Field(default_factory=dict, exclude=True)
    """詳細テキスト用の変更前後の値。"""
    attribute_changes: dict[str, JsonValue] = Field(default_factory=dict, exclude=True)
    """詳細テキスト用の属性の追加・削除・変更。"""


class AnnotationsDiff(BaseModel):
    """アノテーションの追加・削除・変更。"""

    added: list[AnnotationKey] = Field(default_factory=list)
    """右側のみに存在するアノテーション。"""
    removed: list[AnnotationKey] = Field(default_factory=list)
    """左側のみに存在するアノテーション。"""
    changed: list[ChangedAnnotation] = Field(default_factory=list)
    """両側に存在して結果が異なるアノテーション。"""


class AnnotationZipDiff(BaseModel):
    """コマンドのJSON出力。"""

    annotations: AnnotationsDiff = Field(default_factory=AnnotationsDiff)
    """アノテーションの差分。"""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_diff(self) -> bool:
        """差分の有無を返す。

        Args:
            なし。

        Returns:
            差分が存在する場合はTrue。
        """
        return bool(self.annotations.added or self.annotations.removed or self.annotations.changed)
