from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | Sequence["JsonValue"] | dict[str, "JsonValue"]


class AnnotationSpecsDiffOutputFormat(Enum):
    """`annotation_specs diff` の出力フォーマット。"""

    TEXT = "text"
    DETAIL_TEXT = "detail_text"
    JSON = "json"
    PRETTY_JSON = "pretty_json"


class ChangedChoice(BaseModel):
    """変更された選択肢の差分。"""

    model_config = ConfigDict(frozen=True)

    choice_id: str
    """選択肢ID"""
    name_ja_changed: bool = False
    """日本語名が変更されたか"""
    name_en_changed: bool = False
    """英語名が変更されたか"""
    name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.name_ja_changed,
                self.name_en_changed,
                self.name_vi_changed,
                self.keybind_changed,
            ]
        )


class ChangedAttribute(BaseModel):
    """変更された属性の差分。"""

    model_config = ConfigDict(frozen=True)

    attribute_id: str
    """属性ID"""
    read_only_changed: bool = False
    """read_only が変更されたか"""
    name_ja_changed: bool = False
    """日本語名が変更されたか"""
    name_en_changed: bool = False
    """英語名が変更されたか"""
    name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""
    type_changed: bool = False
    """属性型が変更されたか"""
    default_changed: bool = False
    """デフォルト値が変更されたか"""
    metadata_changed: bool = False
    """metadata が変更されたか"""
    choices_changed: bool = False
    """選択肢に変更があるか"""
    choices_order_changed: bool = False
    """選択肢の順序が変更されたか"""
    added_choice_ids: list[str] = Field(default_factory=list)
    """追加された選択肢ID一覧"""
    removed_choice_ids: list[str] = Field(default_factory=list)
    """削除された選択肢ID一覧"""
    changed_choices: list[ChangedChoice] = Field(default_factory=list)
    """変更された既存選択肢の差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.read_only_changed,
                self.name_ja_changed,
                self.name_en_changed,
                self.name_vi_changed,
                self.keybind_changed,
                self.type_changed,
                self.default_changed,
                self.metadata_changed,
                self.choices_changed,
                self.choices_order_changed,
                len(self.added_choice_ids) > 0,
                len(self.removed_choice_ids) > 0,
                len(self.changed_choices) > 0,
            ]
        )


class AttributesDiff(BaseModel):
    """属性一覧の差分。"""

    model_config = ConfigDict(frozen=True)

    added_attribute_ids: list[str] = Field(default_factory=list)
    """追加された属性ID一覧"""
    removed_attribute_ids: list[str] = Field(default_factory=list)
    """削除された属性ID一覧"""
    changed_attributes: list[ChangedAttribute] = Field(default_factory=list)
    """変更された既存属性の差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                len(self.added_attribute_ids) > 0,
                len(self.removed_attribute_ids) > 0,
                len(self.changed_attributes) > 0,
            ]
        )


class ChangedLabel(BaseModel):
    """変更されたラベルの差分。"""

    model_config = ConfigDict(frozen=True)

    label_id: str
    """ラベルID"""
    color_changed: bool = False
    """色が変更されたか"""
    keybind_changed: bool = False
    """キーバインドが変更されたか"""
    label_name_ja_changed: bool = False
    """日本語名が変更されたか"""
    label_name_en_changed: bool = False
    """英語名が変更されたか"""
    label_name_vi_changed: bool = False
    """ベトナム語名が変更されたか"""
    attributes_changed: bool = False
    """紐づく属性に変更があるか"""
    attributes_order_changed: bool = False
    """紐づく属性の順序が変更されたか"""
    added_attribute_ids: list[str] = Field(default_factory=list)
    """追加された属性ID一覧"""
    removed_attribute_ids: list[str] = Field(default_factory=list)
    """削除された属性ID一覧"""
    field_values_changed: bool = False
    """field_values が変更されたか"""
    metadata_changed: bool = False
    """metadata が変更されたか"""
    annotation_type_changed: bool = False
    """annotation_type が変更されたか"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.color_changed,
                self.keybind_changed,
                self.label_name_ja_changed,
                self.label_name_en_changed,
                self.label_name_vi_changed,
                self.attributes_changed,
                self.attributes_order_changed,
                len(self.added_attribute_ids) > 0,
                len(self.removed_attribute_ids) > 0,
                self.field_values_changed,
                self.metadata_changed,
                self.annotation_type_changed,
            ]
        )


class LabelsDiff(BaseModel):
    """ラベル一覧の差分。"""

    model_config = ConfigDict(frozen=True)

    label_order_changed: bool = False
    """ラベル全体の順序が変更されたか"""
    added_label_ids: list[str] = Field(default_factory=list)
    """追加されたラベルID一覧"""
    removed_label_ids: list[str] = Field(default_factory=list)
    """削除されたラベルID一覧"""
    changed_labels: list[ChangedLabel] = Field(default_factory=list)
    """変更された既存ラベルの差分一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.label_order_changed,
                len(self.added_label_ids) > 0,
                len(self.removed_label_ids) > 0,
                len(self.changed_labels) > 0,
            ]
        )


class AttributeRestrictionDiffItem(BaseModel):
    """差分対象の属性制約。"""

    model_config = ConfigDict(frozen=True)

    condition: dict[str, Any]
    """制約条件"""


class ChangedAttributeRestriction(BaseModel):
    """属性ごとの制約差分。"""

    model_config = ConfigDict(frozen=True)

    attribute_id: str
    """属性ID"""
    added_restrictions: list[AttributeRestrictionDiffItem] = Field(default_factory=list)
    """追加された属性制約一覧"""
    removed_restrictions: list[AttributeRestrictionDiffItem] = Field(default_factory=list)
    """削除された属性制約一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                len(self.added_restrictions) > 0,
                len(self.removed_restrictions) > 0,
            ]
        )


class AttributeRestrictionsDiff(BaseModel):
    """属性制約一覧の差分。"""

    model_config = ConfigDict(frozen=True)

    changed_attribute_restrictions: list[ChangedAttributeRestriction] = Field(default_factory=list)
    """変更された属性制約一覧"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return len(self.changed_attribute_restrictions) > 0


class AnnotationSpecsDiff(BaseModel):
    """アノテーション仕様の差分。"""

    model_config = ConfigDict(frozen=True)

    labels: LabelsDiff | None = None
    """ラベル差分"""
    attributes: AttributesDiff | None = None
    """属性差分"""
    attribute_restrictions: AttributeRestrictionsDiff | None = None
    """属性制約差分"""

    def has_changes(self) -> bool:
        """変更有無を返す。"""
        return any(
            [
                self.labels is not None and self.labels.has_changes(),
                self.attributes is not None and self.attributes.has_changes(),
                self.attribute_restrictions is not None and self.attribute_restrictions.has_changes(),
            ]
        )
